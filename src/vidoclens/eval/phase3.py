"""Audit all Phase 3 evidence and summarize all seeds without cherry-picking."""

import argparse
import json
import math
import statistics
import tempfile
from pathlib import Path

from vidoclens.common.pilot import percentile, sha256, write_json
from vidoclens.contracts.phase3 import Phase3Continuation
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.continuation import expected_runs, resolve, verify_logs
from vidoclens.eval.student import choose_checkpoint, evaluate
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.data import load_plan, safe_path


def summarize(values):
    return {
        "values": values,
        "mean": statistics.mean(values),
        "sample_std": statistics.stdev(values),
    }


def verify_profile(profile, config):
    if any(
        profile[name] != expected
        for name, expected in {
            "model_id": config.model_id,
            "revision": config.revision,
            "weights_sha256": config.weights_sha256,
            "attention_backend": config.attention_backend,
            "deterministic_algorithms": config.deterministic_algorithms,
        }.items()
    ):
        raise ValueError("runtime profile differs from frozen configuration")


def verify_sources(root, run, directory=None):
    sources = (
        run.get("source_hashes", {})
        if directory is None
        else {p.name.removeprefix("source_"): sha256(p) for p in directory.glob("source_*.py")}
    )
    expected = {p.name for p in (root / "src/vidoclens/student").glob("*.py")}
    if set(sources) != expected or any(
        sha256(root / "src/vidoclens/student" / name) != digest for name, digest in sources.items()
    ):
        raise ValueError("training/inference source changed since execution")


def verify_training_config(directory, config):
    # Plan created on Windows and runtime copy on Linux may use CRLF vs LF.
    # Both files retain their own byte hashes; compare validated config values here.
    actual = type(config).model_validate_json((directory / "config.json").read_text())
    if actual != config:
        raise ValueError("training configuration changed")


def run(root, plan_dir, campaign_dir, checks_path, output, continuation_path=None):
    root = root.resolve()
    plan_dir, campaign_dir = safe_path(root, plan_dir), safe_path(root, campaign_dir)
    output = safe_path(root, output)
    if output.exists():
        raise ValueError("audit output already exists")
    config, train, dev, _ = load_plan(root, plan_dir)
    plan_hash = sha256(plan_dir / "manifest.json")
    total = math.ceil(len(train) * config.epochs / config.gradient_accumulation)
    expected = expected_runs(config.seeds, total)
    campaign = json.loads((campaign_dir / "campaign.json").read_text())
    if continuation_path is not None:
        continuation_path = safe_path(root, continuation_path)
        continuation = Phase3Continuation.model_validate_json(continuation_path.read_text())
        if safe_path(root, continuation.parent_campaign.path) != campaign_dir / "campaign.json":
            raise ValueError("continuation references a different campaign")
        campaign, directories = resolve(root, continuation, expected, plan_hash)
    else:
        if (
            not campaign["complete"]
            or campaign["plan_sha256"] != plan_hash
            or any(s["exit_code"] != 0 for s in campaign["steps"])
        ):
            raise ValueError("campaign incomplete or failed; verified continuation required")
        verify_logs(campaign_dir, campaign["steps"])
        directories = {name: campaign_dir / name for name in expected}
    for name in ["preflight", "resume_proof", "protocol"]:
        if sha256(safe_path(root, campaign[name])) != campaign[name + "_sha256"]:
            raise ValueError("campaign gate evidence changed")
    preflight = json.loads((root / campaign["preflight"]).read_text())
    resume = json.loads((root / campaign["resume_proof"]).read_text())
    protocol = json.loads((root / campaign["protocol"]).read_text())
    if any(e["plan_sha256"] != plan_hash for e in (preflight, resume, protocol)):
        raise ValueError("gate evidence belongs to another plan")
    checks = json.loads((root / checks_path).read_text())
    required_sources = {
        p.relative_to(root).as_posix() for p in (root / "src/vidoclens/student").glob("*.py")
    } | {
        "src/vidoclens/contracts/student.py",
        "src/vidoclens/contracts/phase3.py",
        "src/vidoclens/eval/student.py",
        "src/vidoclens/eval/phase3.py",
        "src/vidoclens/eval/continuation.py",
    }
    if not required_sources <= checks.get("code_sha256", {}).keys() or any(
        sha256(safe_path(root, name)) != digest for name, digest in checks["code_sha256"].items()
    ):
        raise ValueError("checks do not match current student implementation")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime_profiles = []

    def metrics(directory):
        m = json.loads((directory / "metrics.json").read_text())
        r = json.loads((directory / "run.json").read_text())
        profile = json.loads((directory / "profile.json").read_text())
        if (
            m["plan_sha256"] != plan_hash
            or m["protocol_sha256"] != campaign["protocol_sha256"]
            or m["run_sha256"] != sha256(directory / "run.json")
            or not r["complete"]
            or r["plan_sha256"] != plan_hash
            or r["completed"] != len(dev)
            or r["expected"] != len(dev)
            or m["checkpoint_sha256"] != r["checkpoint_sha256"]
            or r["predictions_sha256"] != sha256(directory / "predictions.jsonl")
            or r["profile_sha256"] != sha256(directory / "profile.json")
            or r["error"] is not None
            or r["gold_in_input"]
            or m["test_or_ood_used"]
            or m["strict"]["n_missing"]
        ):
            raise ValueError("metric/inference evidence mismatch")
        verify_profile(profile, config)
        verify_sources(root, r)
        runtime_profiles.append(profile)
        # Recompute from immutable predictions; never trust or rewrite a cached score.
        with tempfile.TemporaryDirectory(prefix="metric-audit-", dir=output.parent) as scratch:
            recalculated = evaluate(
                root,
                plan_dir,
                directory,
                Path(campaign["protocol"]),
                Path(scratch) / "metrics.json",
            )
        if recalculated != m:
            raise ValueError("stored metrics differ from raw prediction replay")
        return m

    baseline = metrics(directories["L1"])
    if baseline["kind"] != "L1" or baseline["checkpoint_sha256"] is not None:
        raise ValueError("L1 must use the unadapted base")
    candidates, selected, operations, evidence = {}, {}, {}, {}
    for seed in config.seeds:
        train_dir = directories[f"L2_seed{seed}"]
        training = json.loads((train_dir / "run.json").read_text())
        profile = json.loads((train_dir / "profile.json").read_text())
        if (
            not training["complete"]
            or training["error"] is not None
            or training["plan_sha256"] != plan_hash
            or training["kind"] != "train"
            or training["seed"] != seed
            or training["config_sha256"] != sha256(plan_dir / "config.json")
            or training["base_revision"] != config.revision
            or training["base_weights_sha256"] != config.weights_sha256
            or training["environment_lock_sha256"] != sha256(root / config.environment_lock)
            or training["last_step"] != total
            or len(training["steps"]) != total
            or training["examples_total"] != len(train) * config.epochs
            or training["unique_training_examples"] != len(train)
            or sum(s["examples"] for s in training["steps"]) != len(train) * config.epochs
        ):
            raise ValueError("seed training budget/coverage incomplete")
        verify_profile(profile, config)
        verify_sources(root, training, train_dir)
        verify_training_config(train_dir, config)
        runtime_profiles.append(profile)
        steps = training["steps"]
        curve = [
            json.loads(line)
            for line in (train_dir / "learning_curve.jsonl").read_text().splitlines()
        ]
        if curve != steps or [s["step"] for s in steps] != list(range(1, total + 1)):
            raise ValueError("learning curve/update sequence changed")
        if any(
            not math.isfinite(s["loss"]) or not math.isfinite(s["grad_norm"]) or s["grad_norm"] <= 0
            for s in steps
        ):
            raise ValueError("invalid learning/gradient trace")
        rows = []
        for cp in training["checkpoints"]:
            path = safe_path(root, cp["path"])
            if sha256(path / "checkpoint.json") != cp["sha256"]:
                raise ValueError("checkpoint manifest changed")
            meta = validate_checkpoint(path, plan_dir)
            step = meta["step"]
            if (
                meta["seed"] != seed
                or meta["kind"] != "train"
                or meta["config_sha256"] != training["config_sha256"]
                or meta["base_revision"] != config.revision
                or meta["base_weights_sha256"] != config.weights_sha256
                or meta["environment_lock_sha256"] != training["environment_lock_sha256"]
            ):
                raise ValueError("checkpoint seed/config/base differs from training")
            m = metrics(directories[f"L2_seed{seed}_step{step}"])
            if m["kind"] != "L2" or m["checkpoint_sha256"] != cp["sha256"]:
                raise ValueError("evaluation used another adapter")
            rows.append({"step": step, "checkpoint": cp["path"], "metrics": m})
        if len(rows) != 2 or {r["step"] for r in rows} != {math.ceil(total / 2), total}:
            raise ValueError("both preregistered checkpoint evaluations required")
        candidates[str(seed)] = rows
        selected[str(seed)] = choose_checkpoint(rows)
        times = [s["seconds"] for s in steps]
        operations[str(seed)] = {
            "updates": total,
            "examples": training["examples_total"],
            "training_seconds": sum(times),
            "p50_update_seconds": percentile(times, 0.5),
            "p95_update_seconds": percentile(times, 0.95),
            "first5_mean_loss": statistics.mean(s["loss"] for s in steps[:5]),
            "last5_mean_loss": statistics.mean(s["loss"] for s in steps[-5:]),
            "peak_allocated_bytes": max(
                profile["load_peak_allocated_bytes"], max(s["peak_allocated_bytes"] for s in steps)
            ),
            "peak_reserved_bytes": max(
                profile["load_peak_reserved_bytes"], max(s["peak_reserved_bytes"] for s in steps)
            ),
            "max_sequence_tokens": max(s["max_sequence_tokens"] for s in steps),
            "max_target_tokens": max(s["max_target_tokens"] for s in steps),
            "max_image_pixels": max(s["max_image_pixels"] for s in steps),
        }
        evidence[str(seed)] = {
            "run_sha256": sha256(train_dir / "run.json"),
            "profile_sha256": sha256(train_dir / "profile.json"),
        }
    means = {
        field: summarize([r["metrics"]["strict"][field] for r in selected.values()])
        for field in ["strict_nfc_em", "strict_nfc_token_f1", "strict_nfc_anls"]
    }
    means["numeric_em"] = summarize([r["metrics"]["numeric_em"] for r in selected.values()])
    paired = {
        seed: group_bootstrap(
            r["metrics"]["scores"],
            baseline["groups"],
            paired_scores=baseline["scores"],
            resamples=protocol["bootstrap_resamples"],
            seed=protocol["bootstrap_seed"],
        )
        for seed, r in selected.items()
    }
    mean_scores = {
        q: statistics.mean(r["metrics"]["scores"][q] for r in selected.values())
        for q in baseline["scores"]
    }
    paired["mean_seed_scores_minus_L1"] = group_bootstrap(
        mean_scores,
        baseline["groups"],
        paired_scores=baseline["scores"],
        resamples=protocol["bootstrap_resamples"],
        seed=protocol["bootstrap_seed"],
    )
    criteria = {
        "full_G10_three_seeds": set(selected) == {"17", "42", "2026"},
        "processor_no_truncation": preflight["status"] == "pass"
        and all(
            preflight["populations"][name]["n"] == n
            and preflight["populations"][name]["truncated"] == 0
            for name, n in [("train", len(train)), ("dev", len(dev))]
        ),
        "real_resume_and_reload": resume["status"] == "pass"
        and resume["fresh_process_reload_tokens_equal"]
        and resume["resume_greedy_tokens_equal"]
        and resume["optimizer_scheduler_rng_restored"],
        "finite_learning_curves": True,
        "no_oom_profile_under_12gb": all(
            o["peak_reserved_bytes"] < 12 * 1024**3 for o in operations.values()
        )
        and all(p["load_peak_reserved_bytes"] < 12 * 1024**3 for p in runtime_profiles)
        and all(
            r["metrics"]["peak_reserved_bytes"] < 12 * 1024**3
            for rows in candidates.values()
            for r in rows
        )
        and baseline["peak_reserved_bytes"] < 12 * 1024**3,
        "L1_L2_same_dev_population": all(
            r["metrics"]["groups"] == baseline["groups"]
            for rows in candidates.values()
            for r in rows
        ),
        "raw_metrics_replayed_and_provenance_verified": True,
        "all_checks_passed": checks["status"] == "pass",
        "no_test_ood_or_API_training": True,
    }
    training_seconds = sum(o["training_seconds"] for o in operations.values())
    report = {
        "gate": "G3",
        "status": "pass" if all(criteria.values()) else "blocked",
        "criteria": criteria,
        "plan_sha256": plan_hash,
        "campaign_sha256": sha256(campaign_dir / "campaign.json"),
        "parent_campaign_complete": campaign["complete"],
        "continuation_sha256": sha256(continuation_path) if continuation_path else None,
        "run_directories": {
            name: path.relative_to(root).as_posix() for name, path in directories.items()
        },
        "checks_sha256": sha256(root / checks_path),
        "L1": baseline,
        "candidates": candidates,
        "selected": selected,
        "seed_statistics": means,
        "paired_comparisons": paired,
        "operations": operations,
        "evidence": evidence,
        "compute": {
            "L2_three_seeds_training_seconds": training_seconds,
            "matched_12_runs_estimated_training_hours": training_seconds * 4 / 3600,
            "estimate_excludes": [
                "silver/OCR generation",
                "evaluation",
                "load/checkpoint I/O",
                "different token lengths",
                "retries",
            ],
        },
        "limitations": [
            "100-component dev subset, not final test",
            "single image/question vs grouped API Phase 2 protocol",
            "group bootstrap does not include training variance; sample std reported separately",
            "local label teacher, silver, verifier and deployment remain future phases",
        ],
    }
    write_json(output, report)
    print(
        json.dumps(
            {"status": report["status"], "criteria": criteria, "mean_EM": means["strict_nfc_em"]}
        ),
        flush=True,
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ["plan-dir", "campaign-dir", "checks-path", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--continuation-path", type=Path)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
