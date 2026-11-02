"""Report the registered OCR oracle on selected G10 training receipts, never test gold."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.models import OCRResult
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_training_examples
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.compatible import PROTOCOL, compatible_scores
from vidoclens.eval.metrics import evaluate_answers
from vidoclens.eval.oracle import SPAN_PROTOCOL, answer_parts, matched_ocr, spans


def run(annotations: Path, split_dir: Path, ocr_dir: Path, output: Path):
    plan = load_frozen_plan(split_dir, 10)
    summary = json.loads((ocr_dir / "summary.json").read_text(encoding="utf-8"))
    selection = json.loads((ocr_dir / "selection.json").read_text(encoding="utf-8"))
    if summary["status"] != "pass" or selection["split_summary_sha256"] != sha256(
        split_dir / "summary.json"
    ):
        raise ValueError("OCR run incomplete or split changed")
    selected = {r["document_id"] for r in selection["images"]}
    if len(selected) != 100 or len(summary["samples"]) != 100:
        raise ValueError("expected full 100-image quality pilot")
    assignments = {a.source_image_id: a for a in plan.assignments}
    examples = [
        e for e in load_training_examples(annotations, plan) if e.question.document_id in selected
    ]
    if {e.question.document_id for e in examples} != selected:
        raise ValueError("pilot is not fully inside authorized G10 training gold")
    candidates = {}
    for row in summary["samples"]:
        file = (ocr_dir / row["ocr_file"]).resolve()
        if not file.is_relative_to(ocr_dir.resolve()) or sha256(file) != row["ocr_sha256"]:
            raise ValueError("OCR output checksum mismatch")
        result = OCRResult.model_validate_json(file.read_text(encoding="utf-8"))
        if result.document_id != row["document_id"] or result.document_id in candidates:
            raise ValueError("duplicate or mismatched OCR document")
        candidates[result.document_id] = spans(result)
    if set(candidates) != selected:
        raise ValueError("OCR population differs from selected population")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "span_protocol.json", SPAN_PROTOCOL)
    records, predictions, references, groups = [], [], [], {}
    counts = Counter()
    for index, example in enumerate(examples):
        q, ref = example.question, example.reference
        result = matched_ocr(candidates[q.document_id], ref.answers)
        raw = ref.answers[0]
        kind = (
            "numeric"
            if any(c.isdigit() for c in raw) and not any(c.isalpha() for c in raw)
            else "hybrid"
            if any(c.isdigit() for c in raw)
            else "text"
        )
        multipart = len(answer_parts(raw)) > 1
        counts[kind] += 1
        counts["multipart"] += multipart
        group = assignments[q.source_image_id].duplicate_group_id
        groups[q.qid] = group
        records.append(
            {
                "qid": q.qid,
                "document_id": q.document_id,
                "group_id": group,
                "answer_type": kind,
                "multipart": multipart,
                **result,
                "compatible": compatible_scores(result["prediction"], ref.answers),
            }
        )
        predictions.append(
            AnswerPrediction(
                qid=q.qid,
                status="answered" if result["prediction"] is not None else "abstained",
                answer_raw=result["prediction"],
            )
        )
        references.append(ref)
        if index % 100 == 0:
            print(f"oracle {index + 1}/{len(examples)}", flush=True)
    with (output / "per_question.jsonl").open("x", encoding="utf-8") as stream:
        for r in records:
            stream.write(json.dumps(r, ensure_ascii=False) + "\n")
    intervals = {
        metric: group_bootstrap({r["qid"]: r["scores"][metric] for r in records}, groups)
        for metric in ("strict_nfc_em", "strict_nfc_token_f1", "strict_nfc_anls")
    }
    slices = defaultdict(list)
    for r in records:
        slices[r["answer_type"]].append(r)
        slices["multipart" if r["multipart"] else "single_part"].append(r)
    report = {
        "status": "pass",
        "population": "100 frozen G10 train_fit receipts; diagnostic only",
        "test_or_ood_evaluated": False,
        "uses_gold": True,
        "deployable_baseline": False,
        "strict": evaluate_answers(references, predictions).model_dump(),
        "compatible_protocol": PROTOCOL,
        "compatible": {
            m: sum(r["compatible"][m] for r in records) / len(records)
            for m in ("accuracy", "set_token_f1", "anls")
        },
        "bootstrap": intervals,
        "counts": dict(counts),
        "slices": {
            s: {"qa": len(v), "exact_span_recall": sum(r["exact_span_recall"] for r in v) / len(v)}
            for s, v in slices.items()
        },
        "span_protocol": SPAN_PROTOCOL,
        "ocr_summary_sha256": sha256(ocr_dir / "summary.json"),
        "split_summary_sha256": sha256(split_dir / "summary.json"),
        "per_question_sha256": sha256(output / "per_question.jsonl"),
        "limitations": [
            "oracle selects with gold; not semantic correctness from OCR agreement",
            "bounded contiguous span universe; not absolute VLM upper bound",
            "ANLS is for the EM/F1-selected span, not maximized ANLS over all spans",
            "training pilot; no final validation/test performance claim",
        ],
    }
    write_json(output / "report.json", report)
    for name in ("phase1.py", "oracle.py", "bootstrap.py", "compatible.py", "metrics.py"):
        (output / ("source_" + name)).write_bytes(Path(__file__).with_name(name).read_bytes())
    print(
        json.dumps({"status": "pass", "qa": len(records), "strict": report["strict"]}), flush=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("annotations", "split-dir", "ocr-dir", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
