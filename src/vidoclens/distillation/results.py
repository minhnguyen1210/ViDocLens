"""Export measured runs and adopt immutable G3 controls with explicit budget accounting."""

import argparse
import json
import math
import tempfile
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.silver import SilverExperiment, SilverPool
from vidoclens.contracts.silver_results import SilverTrainingResult
from vidoclens.distillation.data import load_plan, profile
from vidoclens.distillation.inputs import g3_evidence
from vidoclens.distillation.sampler import exposure_counts, schedule_digest
from vidoclens.distillation.train import sample_schedule
from vidoclens.eval.phase3 import verify_profile, verify_sources, verify_training_config
from vidoclens.eval.student import choose_checkpoint, evaluate
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.data import safe_path


def checked_predictions(root, plan, directory, protocol):
    saved = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="phase4-metric-replay-") as temporary:
        actual = evaluate(root, plan, directory, protocol, Path(temporary) / "metrics.json")
    if actual != saved:
        raise ValueError("stored metrics differ from raw prediction replay")
    rows = [
        json.loads(s)
        for s in (directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return actual, tuple(
        AnswerPrediction(**{k: r[k] for k in ("qid", "status", "answer_raw")}) for r in rows
    )


def training_records(root, directory, config, *, phase3=False):
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    steps = run["steps"]
    if (
        not run["complete"]
        or run["kind"] != "train"
        or run["start_step"] != 0
        or run["last_step"] != 191
        or [r["step"] for r in steps] != list(range(1, 192))
    ):
        raise ValueError(
            "full uninterrupted 191-update trajectory required; resolve continuation separately"
        )
    if any(
        not all(math.isfinite(r[k]) and r[k] > 0 for k in ("loss", "grad_norm", "seconds"))
        for r in steps
    ):
        raise ValueError("invalid measured training trajectory")
    expected_sizes = [16] * 190 + [13 if phase3 else 16]
    if [r["examples"] for r in steps] != expected_sizes:
        raise ValueError("measured update batch sizes differ from preregistered budget")
    actual_profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
    verify_profile(actual_profile, config)
    verify_training_config(directory, config)
    if phase3:
        verify_sources(root, run, directory)
    return run, sum(s["seconds"] for s in steps), max(s["peak_reserved_bytes"] for s in steps)


def export(root, plans, campaign, output):
    root = root.resolve()
    plans, campaign, output = (root / p for p in (plans, campaign, output))
    recipe = profile(root)
    g3, cohort = g3_evidence(root)
    training_pool = read_model(root / "artifacts/phase4/inputs_v1/train_fit.json", SilverPool)
    evaluation_pool = read_model(root / "artifacts/phase4/inputs_v1/dev_select.json", SilverPool)
    profile_hash = sha256(plans / "training_profile.json")
    common = dict(
        fixture_only=False,
        training_pool_sha256=digest(training_pool),
        evaluation_pool_sha256=digest(evaluation_pool),
        training_profile_sha256=profile_hash,
        evaluation_profile_sha256=sha256(cohort),
        g3_evidence_sha256=recipe.g3_evidence_sha256,
        optimizer_updates_completed=191,
    )
    output.mkdir(parents=True, exist_ok=False)
    evidence, results = {}, []
    gold_qids = tuple(sorted(s.question.qid for s in training_pool.gold_samples))
    for seed in (17, 42, 2026):
        selected = g3["selected"][str(seed)]
        directory = safe_path(root, g3["run_directories"][f"L2_seed{seed}"])
        _, seconds, peak = training_records(root, directory, recipe.student, phase3=True)
        checkpoint = safe_path(root, selected["checkpoint"])
        cp = validate_checkpoint(checkpoint, root / "artifacts/phase3/data_v2")
        if cp["step"] != 191:
            raise ValueError("historical G3 adoption expects its selected end-of-epoch checkpoint")
        inference = safe_path(root, g3["run_directories"][f"L2_seed{seed}_step{cp['step']}"])
        metrics, predictions = checked_predictions(
            root, root / "artifacts/phase3/data_v2", inference, cohort
        )
        if metrics != selected["metrics"]:
            raise ValueError("G3 selected metric changed")
        result = SilverTrainingResult(
            **common,
            arm="L2",
            seed=seed,
            run_id=f"G3-L2-{seed}",
            selection_sha256=None,
            checkpoint_sha256=sha256(checkpoint / "checkpoint.json"),
            gold_qids=gold_qids,
            gold_exposure_counts=dict.fromkeys(gold_qids, 1),
            silver_exposure_counts={},
            selected_checkpoint_step=191,
            selected_gold_exposure_counts=dict.fromkeys(gold_qids, 1),
            selected_silver_exposure_counts={},
            training_seconds=seconds,
            peak_reserved_bytes=peak,
            predictions=predictions,
        )
        results.append(result)
        evidence[result.run_id] = {
            "g3_selected_step": cp["step"],
            "adopted_without_retraining": True,
            "training_run_sha256": sha256(directory / "run.json"),
            "inference_run_sha256": sha256(inference / "run.json"),
        }
    for arm in ("P1-full", "P1-size", "P2"):
        for seed in (17, 42, 2026):
            label = f"{arm}-{seed}"
            plan, directory = plans / label, campaign / label
            config, rows, _, manifest = load_plan(root, plan)
            selection = read_model(plan / "selection.json", SilverExperiment)
            training, seconds, peak = training_records(root, directory, config)
            order = sample_schedule(rows, config, seed, "train")
            counts = exposure_counts(rows, order)
            if (
                training["exposures"] != counts
                or training["schedule_sha256"] != schedule_digest(rows, order)
                or training["plan_sha256"] != sha256(plan / "manifest.json")
                or training["source_hashes"] != manifest["source_hashes"]
            ):
                raise ValueError("training/source/sampler evidence mismatch")
            candidates, evaluated = [], {}
            for step in (96, 191):
                checkpoint = directory / f"checkpoint-{step:04d}"
                cp = validate_checkpoint(checkpoint, plan)
                expected_counts = exposure_counts(rows, order[: step * 16])
                if cp["exposures"] != expected_counts or cp["schedule_sha256"] != schedule_digest(
                    rows, order
                ):
                    raise ValueError("checkpoint exposure evidence mismatch")
                inference = campaign / f"{label}-step{step}"
                metrics, predictions = checked_predictions(
                    root, plan, inference, plan / "dev_protocol.json"
                )
                if metrics["checkpoint_sha256"] != sha256(checkpoint / "checkpoint.json"):
                    raise ValueError("evaluation uses an unexpected checkpoint")
                candidates.append(
                    {
                        "step": step,
                        "checkpoint": checkpoint.relative_to(root).as_posix(),
                        "metrics": metrics,
                    }
                )
                evaluated[step] = (predictions, expected_counts)
            chosen = choose_checkpoint(candidates)
            predictions, prefix = evaluated[chosen["step"]]
            checkpoint = root / chosen["checkpoint"]
            result = SilverTrainingResult(
                **common,
                arm=arm,
                seed=seed,
                run_id=f"P4-{label}",
                selection_sha256=digest(selection),
                checkpoint_sha256=sha256(checkpoint / "checkpoint.json"),
                gold_qids=selection.gold_qids,
                silver_qids=selection.silver_qids,
                gold_exposure_counts=counts["gold"],
                silver_exposure_counts=counts["silver"],
                selected_checkpoint_step=chosen["step"],
                selected_gold_exposure_counts=prefix["gold"],
                selected_silver_exposure_counts=prefix["silver"],
                training_seconds=seconds,
                peak_reserved_bytes=peak,
                predictions=predictions,
            )
            results.append(result)
            evidence[result.run_id] = {
                "selected": chosen,
                "candidates": candidates,
                "training_run_sha256": sha256(directory / "run.json"),
            }
    for result in results:
        write_model(output / f"{result.arm}-{result.seed}.json", result)
    write_model(output / "evidence.json", evidence)
    write_model(
        output / "manifest.json",
        {
            "complete": True,
            "results": len(results),
            "files": {p.name: sha256(p) for p in output.glob("*.json")},
            "l2_rounding_difference_examples": 3,
            "primary_comparison": "P2_vs_P1-size",
        },
    )
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ("plans", "campaign", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    export(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
