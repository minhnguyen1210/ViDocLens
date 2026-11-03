"""Offline student evaluator, numeric membership freeze and checkpoint selection."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from vidoclens.common.pilot import percentile, sha256, write_json
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.compatible import PROTOCOL, compatible_scores
from vidoclens.eval.metrics import evaluate_answers, exact_match
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.student.predict import load_inputs


def numeric_reference(value):
    return any(c.isdigit() for c in value) and not any(c.isalpha() for c in value)


def references(root, plan_dir):
    _, rows = load_inputs(root, plan_dir)
    qids = {r.question.qid for r in rows}
    plan = load_frozen_plan(root / "data/splits/receiptvqa_containment_v1", 10)
    refs = [
        r
        for r in load_evaluation_gold(
            root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", plan, partition="dev_select"
        )
        if r.qid in qids
    ]
    if {r.qid for r in refs} != qids:
        raise ValueError("dev gold population mismatch")
    return rows, refs


def freeze(root, plan_dir, output):
    rows, refs = references(root, root / plan_dir)
    report = {
        "protocol": "phase3_dev_v1",
        "plan_sha256": sha256(root / plan_dir / "manifest.json"),
        "numeric_rule": "any Unicode digit and no alphabetic character in full gold reference",
        "numeric_qids": sorted(r.qid for r in refs if all(numeric_reference(a) for a in r.answers)),
        "qids": sorted(r.qid for r in refs),
        "groups": {r.question.qid: r.duplicate_group_id for r in rows},
        "checkpoint_rule": ["strict_nfc_em_desc", "numeric_em_desc", "p50_seconds_asc", "step_asc"],
        "bootstrap_resamples": 2000,
        "bootstrap_seed": 42,
        "training_seeds": [17, 42, 2026],
        "test_or_ood_used": False,
    }
    write_json(root / output, report)
    print(
        json.dumps(
            {
                "qids": len(refs),
                "numeric_qids": len(report["numeric_qids"]),
                "protocol_sha256": sha256(root / output),
            }
        )
    )


def evaluate(root, plan_dir, run_dir, protocol_path, output):
    plan_dir, run_dir = root / plan_dir, root / run_dir
    protocol_path = root / protocol_path
    protocol = json.loads(protocol_path.read_text())
    run = json.loads((run_dir / "run.json").read_text())
    plan_hash = sha256(plan_dir / "manifest.json")
    if (
        not run["complete"]
        or run["plan_sha256"] != plan_hash
        or protocol["plan_sha256"] != plan_hash
    ):
        raise ValueError("inference incomplete or belongs to another frozen plan")
    if run["predictions_sha256"] != sha256(run_dir / "predictions.jsonl"):
        raise ValueError("prediction hash mismatch")
    rows, refs = references(root, plan_dir)
    predictions = [
        json.loads(s)
        for s in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    parsed = [
        AnswerPrediction(**{k: r[k] for k in ("qid", "status", "answer_raw")}) for r in predictions
    ]
    strict = evaluate_answers(refs, parsed).model_dump(mode="json")
    if strict["n_missing"] or sorted(p.qid for p in parsed) != protocol["qids"]:
        raise ValueError("inference/selection population incomplete")
    by_qid = {p.qid: p.answer_raw for p in parsed}
    numeric = set(protocol["numeric_qids"])
    if numeric != {r.qid for r in refs if all(numeric_reference(a) for a in r.answers)}:
        raise ValueError("numeric membership changed after freeze")
    scores = {
        r.qid: max(exact_match(by_qid[r.qid], a) for a in r.answers)
        if by_qid[r.qid] is not None
        else 0.0
        for r in refs
    }
    compatible = Counter()
    for ref in refs:
        compatible.update(compatible_scores(by_qid[ref.qid], ref.answers))
    groups = {r.question.qid: r.duplicate_group_id for r in rows}
    if groups != protocol["groups"]:
        raise ValueError("evaluation groups differ from frozen protocol")
    documents = {r.question.qid: r.question.document_id for r in rows}
    macro = defaultdict(list)
    for qid, value in scores.items():
        macro[documents[qid]].append(value)
    times = [r["seconds"] for r in predictions]
    report = {
        "kind": run["kind"],
        "run_sha256": sha256(run_dir / "run.json"),
        "checkpoint_sha256": run["checkpoint_sha256"],
        "plan_sha256": plan_hash,
        "protocol_sha256": sha256(protocol_path),
        "strict": strict,
        "numeric_n": len(numeric),
        "numeric_em": sum(scores[q] for q in numeric) / len(numeric) if numeric else None,
        "compatible_protocol": PROTOCOL,
        "compatible": {k: v / len(refs) for k, v in compatible.items()},
        "strict_em_ci": group_bootstrap(
            scores,
            groups,
            resamples=protocol["bootstrap_resamples"],
            seed=protocol["bootstrap_seed"],
        ),
        "image_macro_em": sum(sum(v) / len(v) for v in macro.values()) / len(macro),
        "p50_seconds": percentile(times, 0.5),
        "p95_seconds": percentile(times, 0.95),
        "total_inference_seconds": sum(times),
        "peak_allocated_bytes": max(r["peak_allocated_bytes"] for r in predictions),
        "peak_reserved_bytes": max(r["peak_reserved_bytes"] for r in predictions),
        "max_input_tokens": max(r["input_tokens"] for r in predictions),
        "max_image_tokens": max(r["image_tokens"] for r in predictions),
        "output_limit_hits": sum(r["hit_output_limit"] for r in predictions),
        "scores": scores,
        "groups": groups,
        "test_or_ood_used": False,
    }
    write_json(root / output, report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "kind",
                    "strict",
                    "numeric_em",
                    "numeric_n",
                    "p50_seconds",
                    "p95_seconds",
                    "output_limit_hits",
                ]
            }
        ),
        flush=True,
    )
    return report


def choose_checkpoint(candidates):
    if not candidates:
        raise ValueError("no checkpoints evaluated")
    return min(
        candidates,
        key=lambda r: (
            -r["metrics"]["strict"]["strict_nfc_em"],
            -(r["metrics"]["numeric_em"] if r["metrics"]["numeric_em"] is not None else -1),
            r["metrics"]["p50_seconds"],
            r["step"],
        ),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["freeze", "evaluate"])
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--plan-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--protocol-path", type=Path)
    a = p.parse_args()
    if a.command == "freeze":
        freeze(a.root.resolve(), a.plan_dir, a.output)
    else:
        if a.run_dir is None or a.protocol_path is None:
            p.error("evaluate requires run-dir and protocol-path")
        evaluate(a.root.resolve(), a.plan_dir, a.run_dir, a.protocol_path, a.output)


if __name__ == "__main__":
    main()
