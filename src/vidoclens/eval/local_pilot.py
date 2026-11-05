"""Evaluate the fixed 666-QA local teacher pilot; never approve using training gold."""

import argparse
import json
from collections import Counter
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.local_teacher import LocalGenerationGrant, LocalTeacherPlan
from vidoclens.contracts.silver import SilverBatch, SilverPool
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.distillation.inputs import g3_evidence, source_paths
from vidoclens.eval.metrics import evaluate_answers
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.pool import make_pool
from vidoclens.teacher.local_labels import run_local


def quality_gate(summary, manifest, l1_em):
    counts = manifest["label_status_counts"]
    requests = manifest["requests"]
    return {
        "complete_cohort": summary["n_questions"] == 666 and summary["n_missing"] == 0,
        "answered_at_least_90_percent": summary["n_answered"] / summary["n_questions"] >= 0.9,
        "no_inference_errors": counts.get("error", 0) == 0,
        "strict_em_at_least_frozen_L1": summary["strict_nfc_em"] >= l1_em,
        "actual_gpu_measurements": bool(requests)
        and all(
            r["generation_seconds"] > 0 and 0 < r["peak_reserved_bytes"] < 12 * 1024**3
            for r in requests
        ),
    }


def run(root, run_dir, output, parsed_dir=None, raw_mode=False):
    root = root.resolve()
    run_dir, output = root / run_dir, root / output
    g3, cohort = g3_evidence(root)
    archive, frozen, inventory = source_paths(root)
    pool = make_pool(archive, frozen, inventory, "dev_select", cohort)
    stored_pool = read_model(root / "artifacts/phase4/inputs_v1/dev_select.json", SilverPool)
    if stored_pool != pool:
        raise ValueError("pilot evaluation population changed")
    plan_type, replay_runner = LocalTeacherPlan, run_local
    if raw_mode:
        from vidoclens.contracts.raw_teacher import RawTeacherPlan
        from vidoclens.teacher.raw_labels import run_local as run_raw

        plan_type, replay_runner = RawTeacherPlan, run_raw
        if parsed_dir is not None:
            raise ValueError("raw generation is not JSON and cannot use the structured reparser")
    plan = read_model(run_dir / "plan.json", plan_type)
    grant = read_model(run_dir / "grant.json", LocalGenerationGrant)
    batch = read_model(run_dir / "batch.json", SilverBatch)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if (
        not manifest.get("complete")
        or batch.fixture_only
        or plan.partition != "dev_select"
        or batch.pool_sha256 != digest(pool)
        or manifest["batch_sha256"] != digest(batch)
        or plan.config.qid_format != ("canonical" if raw_mode else "request_local_v1")
    ):
        raise ValueError("pilot needs complete real unchanged local run")
    mapping = json.loads(
        (root / "artifacts/phase4/teacher_protocol_v1/dev_select_image_map.json").read_text(
            encoding="utf-8"
        )
    )
    images = {d: root / "artifacts/phase4/inputs_v1" / p for d, p in mapping.items()}

    class ReplayOnly:
        fixture_only = False

        def generate(self, request, image):
            raise AssertionError("completed pilot replay must never call a model")

    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    replay, replay_summary = replay_runner(
        pool,
        plan,
        grant,
        ReplayOnly(),
        images,
        environment,
        run_dir,
        run_id=batch.run_id,
        max_attempts=1,
    )
    if replay != batch or replay_summary["new_calls"]:
        raise ValueError("pilot raw cache replay mismatch")
    original_batch = batch
    parser_manifest_sha256 = None
    if parsed_dir is not None:
        from vidoclens.teacher.reparse import verify

        parsed_dir = root / parsed_dir
        batch, _ = verify(run_dir, parsed_dir)
        parser_manifest_sha256 = sha256(parsed_dir / "manifest.json")
    qids = {s.question.qid for s in pool.samples}
    gold = [
        r
        for r in load_evaluation_gold(archive, load_frozen_plan(frozen, 10), partition="dev_select")
        if r.qid in qids
    ]
    predictions = [
        AnswerPrediction(
            qid=label.qid,
            status="answered"
            if label.status == "answered"
            else "abstained"
            if label.status == "unanswerable"
            else "error",
            answer_raw=label.answer_raw,
        )
        for label in batch.labels
    ]
    summary = evaluate_answers(gold, predictions).model_dump(mode="json")
    effective_manifest = manifest | {
        "label_status_counts": dict(Counter(label.status for label in batch.labels))
    }
    criteria = quality_gate(summary, effective_manifest, g3["L1"]["strict"]["strict_nfc_em"])
    report = {
        "protocol": "phase4_local_teacher_pilot_v1",
        "source_run": run_dir.relative_to(root).as_posix(),
        "generation_mode": "raw_single_v1" if raw_mode else "structured_batch_v1",
        "generation_config": plan.config.model_dump(mode="json"),
        "status": "pass" if all(criteria.values()) else "fail",
        "criteria": criteria,
        "strict": summary,
        "status_counts": dict(Counter(label.status for label in batch.labels)),
        "pool_sha256": digest(pool),
        "plan_sha256": digest(plan),
        "batch_sha256": digest(batch),
        "source_batch_sha256": digest(original_batch),
        "source_status_counts": dict(Counter(label.status for label in original_batch.labels)),
        "parser_policy": "raw_answer_or_sentinel_v1"
        if raw_mode
        else "strict_item_reparse_v1"
        if parsed_dir
        else "strict_whole_batch_v1",
        "parser_manifest_sha256": parser_manifest_sha256,
        "run_manifest_sha256": sha256(run_dir / "manifest.json"),
        "g3_sha256": sha256(root / "artifacts/phase3/g3_report_v1.json"),
        "cohort_sha256": sha256(cohort),
        "zero_call_replay": True,
        "generation_seconds": sum(r["generation_seconds"] for r in manifest["requests"]),
        "peak_reserved_bytes": max(r["peak_reserved_bytes"] for r in manifest["requests"]),
        "test_ood_calibrate_used": False,
        "limitations": [
            "dev selection only",
            "offline labeling generation time, not end-to-end serving latency",
            "quality viability threshold does not prove teacher exceeds L2",
        ],
    }
    write_model(output, report)
    print(
        json.dumps({"status": report["status"], "criteria": criteria, "strict": summary}),
        flush=True,
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--parsed-dir", type=Path)
    p.add_argument("--raw-mode", action="store_true")
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
