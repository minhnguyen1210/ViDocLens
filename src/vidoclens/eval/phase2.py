"""Finalize Phase 2 from immutable live runs, replay evidence and offline checks.

No provider access. Gold is opened only here for dev_select evaluation.
"""

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from vidoclens.common.pilot import percentile, sha256, write_json
from vidoclens.contracts.teacher import TeacherPermission, TeacherResult
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.metrics import exact_match
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.eval.teacher import evaluate_teacher
from vidoclens.teacher.ledger import Ledger
from vidoclens.teacher.planning import read_plan
from vidoclens.teacher.requests import request_key

EXPERIMENTS = {"pilot", "A1", "A2", "A3", "A5"}


def select_roles(metrics, operations, policy):
    """Predeclared quality/cost ordering, independent of model names or test labels."""
    if set(metrics) != {"A1", "A2", "A3", "A5"}:
        raise ValueError("all four mandatory baseline metrics are required")

    def rank(name):
        return (
            -metrics[name]["strict"]["strict_nfc_em"],
            -metrics[name]["strict"]["strict_nfc_anls"],
            operations[name]["spent_usd"] / metrics[name]["strict"]["n_questions"],
            name,
        )

    benchmark = min(policy["benchmark_candidates"], key=rank)
    strong = min(policy["fallback_strong_candidates"], key=rank)
    cheap = policy["fallback_cheap_candidate"]
    delta = metrics[strong]["strict"]["strict_nfc_em"] - metrics[cheap]["strict"]["strict_nfc_em"]
    cheaper = operations[cheap]["spent_usd"] < operations[strong]["spent_usd"]
    fallback = cheap if delta <= policy["fallback_max_em_drop"] + 1e-12 and cheaper else strong
    return {
        "benchmark_experiment": benchmark,
        "fallback_experiment": fallback,
        "fallback_strong_comparator": strong,
        "cheap_em_drop": delta,
        "cheap_is_less_expensive": cheaper,
        "label_strategy": policy["label_strategy"],
        "api_training_export_allowed": False,
        "label_teacher_ready_for_silver": False,
        "cascade_ready": False,
        "selection_population": "100 frozen dev_select components, 666 QA",
    }


def read_run(directory: Path, expected: set[str], plan_hash: str):
    report = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    if report["source"] != "openai_responses" or report["plan_sha256"] != plan_hash:
        raise ValueError("run source/plan mismatch")
    results = {}
    for name, checksum in report["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or sha256(path) != checksum:
            raise ValueError("result path/checksum mismatch")
        result = TeacherResult.model_validate_json(path.read_text(encoding="utf-8"))
        if result.request_key in results or name != f"{result.request_key}.json":
            raise ValueError("duplicate or mismatched result identity")
        results[result.request_key] = result
    if not report["complete"] or set(results) != expected or report["expected"] != len(expected):
        raise ValueError("experiment is incomplete or has different requests")
    samples = report["samples"]
    if (
        report["completed"] != len(expected)
        or report["status_counts"] != dict(Counter(r.status for r in results.values()))
        or len(samples) != len(expected)
        or {s["request_key"] for s in samples} != expected
        or report["cache_hits"] != sum(s["cache_hit"] for s in samples)
    ):
        raise ValueError("run counters/samples do not match results")
    return report, results


def finalize(
    root: Path,
    plan_dir: Path,
    live_dirs: list[Path],
    replay_dirs: list[Path],
    permission_path: Path,
    checks_path: Path,
    output: Path,
):
    output = root / output
    requests, prompt, manifest = read_plan(root / plan_dir, root)
    plan_hash = sha256(root / plan_dir / "manifest.json")
    policy_path = root / "configs/teacher/selection_v1.json"
    freeze_path = root / "artifacts/phase2/selection_policy_freeze_v1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        freeze["selection_policy_sha256"] != sha256(policy_path)
        or freeze["plan_sha256"] != plan_hash
    ):
        raise ValueError("selection policy changed after freeze")
    permission = TeacherPermission.model_validate_json(
        (root / permission_path).read_text(encoding="utf-8")
    )
    expected = {
        experiment: {request_key(r, prompt) for r in requests if r.experiment == experiment}
        for experiment in EXPERIMENTS
    }
    if set(permission.allowed_request_keys) != set().union(*expected.values()):
        raise ValueError("approval scope differs from this experiment campaign")
    reports, results, original_hashes = {}, {}, {}
    for directory in live_dirs:
        directory = root / directory
        exp = json.loads((directory / "run.json").read_text(encoding="utf-8"))["experiment"]
        if exp not in expected or exp in reports:
            raise ValueError("unknown or duplicate live experiment")
        report, rows = read_run(directory, expected[exp], plan_hash)
        if report["permission_sha256"] != sha256(root / permission_path):
            raise ValueError("run used another grant")
        reports[exp] = report
        results.update(rows)
        original_hashes[exp] = report["files"]
    if set(reports) != EXPERIMENTS:
        raise ValueError("five live experiments required")
    replays = {}
    for directory in replay_dirs:
        directory = root / directory
        exp = json.loads((directory / "run.json").read_text(encoding="utf-8"))["experiment"]
        if exp not in expected or exp in replays:
            raise ValueError("unknown or duplicate replay experiment")
        report, _ = read_run(directory, expected[exp], plan_hash)
        unchanged = all(
            report["ledger_before"][field] == report["ledger"][field]
            for field in (
                "attempts",
                "spent_micro_usd",
                "reserved_micro_usd",
                "uncertain_micro_usd",
            )
        )
        replays[exp] = {
            "all_cache_hits": report["cache_hits"] == len(expected[exp]),
            "ledger_unchanged": unchanged,
            "identical_result_files": report["files"] == original_hashes[exp],
            "run_sha256": sha256(directory / "run.json"),
        }
    if set(replays) != EXPERIMENTS:
        raise ValueError("five replay experiments required")
    ledger_path = root / "cache/teacher/phase2.sqlite"
    ledger = Ledger(ledger_path, permission.budget_micro_usd)
    accounting = ledger.summary()
    for key, result in results.items():
        if ledger.cached(key) != result:
            raise ValueError("result differs from durable provider cache")
    with sqlite3.connect(ledger_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        attempts = db.execute("SELECT key,status,actual FROM attempts").fetchall()
    if any(key not in results for key, _, _ in attempts):
        raise ValueError("ledger contains another campaign; attribution must be reconciled")
    operations = {}
    for exp in sorted(EXPERIMENTS):
        calls = [(status, actual) for key, status, actual in attempts if key in expected[exp]]
        rows = [results[key] for key in expected[exp]]
        samples = reports[exp]["samples"]
        times = [sample["wall_seconds"] for sample in samples if not sample["cache_hit"]]
        usages = [row.usage for row in rows if row.usage is not None]
        operations[exp] = {
            "requests": len(rows),
            "attempts": len(calls),
            "images": len({r.document_id for r in requests if r.experiment == exp}),
            "question_count": sum(len(r.questions) for r in requests if r.experiment == exp),
            "status_counts": dict(Counter(row.status for row in rows)),
            "accounting_states": dict(Counter(status for status, _ in calls)),
            "spent_usd": sum(actual or 0 for status, actual in calls if status == "spent")
            / 1_000_000,
            "input_tokens": sum(u.input_tokens for u in usages),
            "cached_input_tokens": sum(u.cached_input_tokens for u in usages),
            "output_tokens": sum(u.output_tokens for u in usages),
            "usage_available_requests": len(usages),
            "p50_uncached_request_seconds": percentile(times, 0.5) if times else None,
            "p95_uncached_request_seconds": percentile(times, 0.95) if times else None,
            "started_at": reports[exp]["started_at"],
            "finished_at": reports[exp]["finished_at"],
            "latency_scope": "validation/cache/network/parse per group; not deployment latency",
        }
    plan = load_frozen_plan(root / "data/splits/receiptvqa_containment_v1", 10)
    refs = load_evaluation_gold(
        root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", plan, partition="dev_select"
    )
    evaluation = evaluate_teacher(requests, list(results.values()), refs, prompt)
    gold = {ref.qid: ref for ref in refs}
    component = {r["source_image_id"]: r["duplicate_group_id"] for r in manifest["selection"]}
    scores, groups = defaultdict(dict), {}
    for request in requests:
        if request.purpose != "dev_baseline":
            continue
        result = results[request_key(request, prompt)]
        answers = {r.qid: r.answer for r in result.labels} if result.status == "ok" else {}
        for query in request.questions:
            answer = answers.get(query.qid)
            scores[request.experiment][query.qid] = (
                max(exact_match(answer, ref) for ref in gold[query.qid].answers)
                if answer is not None
                else 0.0
            )
            groups[query.qid] = component[request.source_image_id]
    statistics = {}
    for exp, values in scores.items():
        by_group = defaultdict(list)
        for qid, score in values.items():
            by_group[groups[qid]].append(score)
        statistics[exp] = {
            "strict_em_ci": group_bootstrap(
                values,
                groups,
                resamples=policy["bootstrap_resamples"],
                seed=policy["bootstrap_seed"],
            ),
            "image_macro_em": sum(sum(v) / len(v) for v in by_group.values()) / len(by_group),
        }
    paired = {
        f"{left}_minus_{right}": group_bootstrap(
            scores[left],
            groups,
            paired_scores=scores[right],
            resamples=policy["bootstrap_resamples"],
            seed=policy["bootstrap_seed"],
        )
        for left, right in policy["paired_comparisons"]
    }
    choices = select_roles(evaluation["metrics"], operations, policy)
    evaluation["role_selection_frozen"] = True
    for role, experiment in (
        ("benchmark_teacher", choices["benchmark_experiment"]),
        ("fallback_teacher", choices["fallback_experiment"]),
    ):
        request = next(r for r in requests if r.experiment == experiment)
        choices[role] = request.profile.model_dump(mode="json") | {"role": role}
    checks = json.loads((root / checks_path).read_text(encoding="utf-8"))
    criteria = {
        "all_live_experiments_complete": set(reports) == EXPERIMENTS,
        "pilot_50_images": operations["pilot"]["images"] == 50,
        "same_100_dev_images": all(operations[e]["images"] == 100 for e in EXPERIMENTS - {"pilot"}),
        "replay_zero_calls_and_spend": all(
            all(r[k] for k in ("all_cache_hits", "ledger_unchanged", "identical_result_files"))
            for r in replays.values()
        ),
        "budget_within_cap_and_settled": not accounting["over_cap"]
        and accounting["reserved_micro_usd"] == accounting["uncertain_micro_usd"] == 0,
        "offline_checks_passed": checks["status"] == "pass",
        "no_test_or_ood_selection": not evaluation["test_or_ood_used"],
        "no_api_training_export": not permission.training_export_allowed,
        "selection_policy_unchanged": freeze["selection_policy_sha256"] == sha256(policy_path),
    }
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "protocol": "phase2_api_v1",
        "gate": "G2",
        "status": "pass" if all(criteria.values()) else "blocked",
        "criteria": criteria,
        "plan_sha256": plan_hash,
        "selection_policy_sha256": sha256(policy_path),
        "permission_sha256": sha256(root / permission_path),
        "checks_sha256": sha256(root / checks_path),
        "live_runs": {
            json.loads((root / directory / "run.json").read_text(encoding="utf-8"))["experiment"]: {
                "directory": directory.as_posix(),
                "run_sha256": sha256(root / directory / "run.json"),
            }
            for directory in live_dirs
        },
        "operations": operations,
        "evaluation": evaluation,
        "statistics": statistics,
        "paired_comparisons": paired,
        "role_decisions": choices,
        "ledger": accounting,
        "replays": replays,
        "limitations": [
            "Dev selection evidence, not final test performance",
            "No API label export; local4B requires pre-Phase4 pilot",
            "No live Batch upload or deployment/cascade validation",
            "API request latency is not deployment latency",
        ],
    }
    write_json(output / "report.json", report)
    write_json(
        output / "role_freeze.json",
        choices
        | {
            "plan_sha256": plan_hash,
            "report_sha256": sha256(output / "report.json"),
            "selection_policy_sha256": sha256(policy_path),
            "gate_status": report["status"],
        },
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--live-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--replay-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--permission-path", type=Path, required=True)
    parser.add_argument("--checks-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = finalize(**vars(parser.parse_args()))
    print(
        json.dumps(
            {
                "status": report["status"],
                "criteria": report["criteria"],
                "spent_usd": report["ledger"]["spent_micro_usd"] / 1_000_000,
            }
        )
    )


if __name__ == "__main__":
    main()
