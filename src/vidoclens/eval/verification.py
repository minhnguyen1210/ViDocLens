"""Privileged dev evaluation: raw student vs check/snap, including harm and coverage."""

from statistics import mean

from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.metrics import evaluate_answers, score_answer
from vidoclens.filtering.io import digest
from vidoclens.verify.bundle import decisions


def references_for(pool, references):
    refs = [GoldReference.model_validate(r.model_dump()) for r in references]
    samples = {s.question.qid: s for s in pool.samples}
    gold = {r.qid: r for r in refs}
    if (
        len(gold) != len(refs)
        or gold.keys() != samples.keys()
        or any(r.document_id != samples[r.qid].question.document_id for r in refs)
    ):
        raise ValueError("gold must cover the exact frozen dev population")
    return refs


def paired_delta(pool, references, first, second, *, resamples=2000, seed=42):
    if resamples < 2:
        raise ValueError("at least two resamples required")
    scores = [
        {r.qid: score_answer(outputs.get(r.qid), r.answers).strict_nfc_em for r in references}
        for outputs in (first, second)
    ]
    groups = {s.question.qid: s.duplicate_group_id for s in pool.samples}
    if len(set(groups.values())) < 2:
        return {
            "point_estimate": mean(scores[0][q] - scores[1][q] for q in groups),
            "lower_95": None,
            "upper_95": None,
            "reason": "fewer_than_two_groups",
        }
    return group_bootstrap(
        scores[0], groups, paired_scores=scores[1], resamples=resamples, seed=seed
    )


def evaluate_verifier(pool, student, ocr, profile, references, *, resamples=2000):
    result = decisions(pool, student, ocr, profile)
    references = references_for(pool, references)
    raw_predictions = [o.prediction for o in student.observations]
    prediction_sets = {"P2": raw_predictions} | {
        variant: [
            AnswerPrediction(qid=d.qid, status=d.status, answer_raw=d.answer_after) for d in rows
        ]
        for variant, rows in result.items()
    }
    outputs = {
        name: {p.qid: p.answer_raw for p in predictions}
        for name, predictions in prediction_sets.items()
    }
    gold = {r.qid: r for r in references}
    snapped = [d for d in result["P3-snap"] if d.snap_applied]
    corrected = harmed = correct_before = 0
    for d in snapped:
        before = score_answer(d.answer_before, gold[d.qid].answers).strict_nfc_em
        after = score_answer(d.answer_after, gold[d.qid].answers).strict_nfc_em
        corrected += before == 0 and after == 1
        harmed += before == 1 and after == 0
        correct_before += before == 1
    # Harm of abstention is separate from altering a previously correct string.
    lost = {
        variant: sum(
            score_answer(outputs["P2"].get(r.qid), r.answers).strict_nfc_em == 1
            and outputs[variant].get(r.qid) is None
            for r in references
        )
        for variant in result
    }
    return {
        "protocol": "verification_dev_report_v1",
        "partition": pool.partition,
        "pool_sha256": digest(pool),
        "student_sha256": digest(student),
        "profile_sha256": digest(profile),
        "reference_sha256": digest(
            [r.model_dump(mode="json") for r in sorted(references, key=lambda r: r.qid)]
        ),
        "fixture_only": profile.binding.fixture_only,
        "metrics": {
            k: evaluate_answers(references, v).model_dump(mode="json")
            for k, v in prediction_sets.items()
        },
        "snap": {
            "attempted_applied": len(snapped),
            "corrected": corrected,
            "harmed": harmed,
            "correct_before_among_snapped": correct_before,
            "correction_precision": corrected / len(snapped) if snapped else None,
            "harm_per_edit": harmed / len(snapped) if snapped else None,
            "harm_among_correct_edited": harmed / correct_before if correct_before else None,
            "numeric_edits": sum(
                any(c.isdigit() for c in (d.answer_before + d.answer_after)) for d in snapped
            ),
        },
        "correct_predictions_abstained": lost,
        "paired_em": {
            "P3-check_vs_P2": paired_delta(
                pool, references, outputs["P3-check"], outputs["P2"], resamples=resamples
            ),
            "P3-snap_vs_P3-check": paired_delta(
                pool, references, outputs["P3-snap"], outputs["P3-check"], resamples=resamples
            ),
        },
        "limitations": [
            "field rules are conservative heuristics, not semantic truth",
            "no probability calibration",
            "no real inference/latency measured by this evaluator",
            "dev findings are not confirmatory test results",
        ],
    }
