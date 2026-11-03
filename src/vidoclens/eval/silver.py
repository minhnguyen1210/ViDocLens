"""Privileged filter audit: gold enters only after rules and predictions are frozen."""

from collections import defaultdict

from vidoclens.contracts.dataset import GoldReference
from vidoclens.eval.metrics import score_answer
from vidoclens.filtering.io import digest
from vidoclens.filtering.pipeline import validate_run


def _rates(rows):
    eligible = [r for r in rows if r[0].f0_keep]
    kept = [r for r in eligible if r[0].f1_keep]
    correct = sum(r[1] for r in eligible)
    kept_correct = sum(r[1] for r in kept)
    return {
        "requested": len(rows),
        "eligible": len(eligible),
        "kept": len(kept),
        "correct_eligible": correct,
        "correct_kept": kept_correct,
        "label_accuracy": correct / len(eligible) if eligible else None,
        "retention": len(kept) / len(eligible) if eligible else None,
        "filter_precision": kept_correct / len(kept) if kept else None,
        "filter_recall": kept_correct / correct if correct else None,
        "false_accept": len(kept) - kept_correct,
        "false_reject": correct - kept_correct,
    }


def audit_filter(pool, batch, run, references, *, quality_bins=None):
    pool, batch, run = validate_run(pool, batch, run)
    if pool.partition not in {"audit_holdout", "dev_select"}:
        raise PermissionError("filter quality evaluation only supports dev_select/audit_holdout")
    if pool.partition == "audit_holdout" and run.config.status != "frozen_dev_select":
        raise PermissionError("holdout cannot select filter rules")
    references = [GoldReference.model_validate(r.model_dump()) for r in references]
    gold = {r.qid: r for r in references}
    samples = {s.question.qid: s for s in pool.samples}
    if len(gold) != len(references) or set(gold) != samples.keys():
        raise ValueError("gold must cover exactly the registered audit/dev pool")
    for qid, reference in gold.items():
        if reference.document_id != samples[qid].question.document_id:
            raise ValueError("gold document identity mismatch")
    if quality_bins is not None and (
        set(quality_bins) != {s.question.document_id for s in pool.samples}
        or any(not isinstance(v, str) or not v.strip() for v in quality_bins.values())
    ):
        raise ValueError("independent OCR quality bins must cover exactly pool documents")
    all_rows, types, questions, outcomes = (
        [],
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    quality = defaultdict(list)
    for d in run.decisions:
        correct = score_answer(d.answer_raw, gold[d.qid].answers).strict_nfc_em == 1
        row = (d, correct)
        all_rows.append(row)
        types[d.answer_type].append(row)
        questions[d.question_type].append(row)
        if quality_bins is not None:
            quality[quality_bins[samples[d.qid].question.document_id]].append(row)
        if d.f0_keep:
            outcomes[
                ("kept_" if d.f1_keep else "rejected_") + ("correct" if correct else "wrong")
            ].append(d.qid)
    return {
        "protocol": "strict_nfc_em_filter_audit_v1",
        "partition": pool.partition,
        "filter_run_sha256": digest(run),
        "config_sha256": digest(run.config),
        "pool_sha256": digest(pool),
        "access_plan_sha256": pool.access_plan_sha256,
        "fixture_only": batch.fixture_only,
        "reference_sha256": digest(
            [r.model_dump(mode="json") for r in sorted(references, key=lambda r: r.qid)]
        ),
        "overall": _rates(all_rows),
        "by_answer_type": {k: _rates(v) for k, v in sorted(types.items())},
        "by_question_type": {k: _rates(v) for k, v in sorted(questions.items())},
        "review_qids": {k: sorted(v) for k, v in sorted(outcomes.items())},
        "ocr_quality_bins": {k: _rates(v) for k, v in sorted(quality.items())}
        if quality_bins is not None
        else None,
        "quality_bins_sha256": digest(quality_bins) if quality_bins is not None else None,
        "limitations": [
            "question types are heuristics",
            "OCR quality bins require independent annotations",
            "human review not performed",
            "no student performance measured",
        ],
    }
