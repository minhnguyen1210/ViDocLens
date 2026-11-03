"""Counterfactual routing on recorded predictions. No claim of live end-to-end latency."""

from vidoclens.common.pilot import percentile
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.eval.metrics import evaluate_answers
from vidoclens.eval.verification import paired_delta, references_for
from vidoclens.filtering.io import digest, revalidate
from vidoclens.verify.bundle import check_batch, decisions


def routing_grid(pool, student, teacher, ocr, profile, plan, references, *, resamples=2000):
    plan = revalidate(plan)
    pool, student, profile = check_batch(pool, student, profile)
    _, teacher, _ = check_batch(pool, teacher, profile)
    if pool.partition != "dev_calibrate" or profile.status != "frozen_dev_select":
        raise PermissionError("routing selection needs dev_calibrate and frozen verifier")
    if (
        student.source != "student"
        or teacher.source != "fallback_teacher"
        or teacher.cache_regime != student.cache_regime
    ):
        raise ValueError("need comparable student/fallback batches with declared same cache regime")
    if (
        plan.pool_sha256 != digest(pool)
        or plan.verifier_profile_sha256 != digest(profile)
        or plan.fixture_only != profile.binding.fixture_only
    ):
        raise ValueError("routing plan provenance mismatch")
    references = references_for(pool, references)
    qids = {r.qid for r in references}
    if not set(plan.external_eligible_qids) <= qids:
        raise ValueError("external eligibility outside pool")
    teacher_obs = {o.prediction.qid: o for o in teacher.observations}
    if teacher_obs.keys() != qids:
        raise ValueError("teacher-all counterfactual needs all qids, including explicit failures")
    student_obs = {o.prediction.qid: o for o in student.observations}
    local = {d.qid: d for d in decisions(pool, student, ocr, profile)["P3-snap"]}
    fallback = {d.qid: d for d in decisions(pool, teacher, ocr, profile)["P3-check"]}
    healthy_ocr = {r.document_id for r in ocr if r.status == "ok" and r.spans}
    samples = {s.question.qid: s for s in pool.samples}
    eligible = set(plan.external_eligible_qids)
    teacher_all_cost = _sum_known(o.cost_micro_usd for o in teacher.observations)
    teacher_raw = evaluate_answers(
        references, [o.prediction for o in teacher.observations]
    ).model_dump(mode="json")
    teacher_verified_predictions = [
        AnswerPrediction(qid=q, status=fallback[q].status, answer_raw=fallback[q].answer_after)
        for q in sorted(qids)
    ]
    teacher_verified = evaluate_answers(references, teacher_verified_predictions).model_dump(
        mode="json"
    )
    points = []
    for threshold in plan.thresholds:
        outputs, calls, local_kept, totals = [], [], 0, []
        for qid in sorted(qids):
            row = student_obs.get(qid)
            answer, status = None, "abstained"
            elapsed = row.latency_ms if row else None
            if local[qid].status == "answered" and local[qid].rule_score >= threshold:
                answer, status = local[qid].answer_after, "answered"
                local_kept += 1
            elif (
                row is not None
                and row.prediction.status != "error"
                and qid in eligible
                and samples[qid].question.document_id in healthy_ocr
            ):
                calls.append(qid)
                answer, status = fallback[qid].answer_after, fallback[qid].status
                elapsed = (
                    elapsed + teacher_obs[qid].latency_ms
                    if elapsed is not None and teacher_obs[qid].latency_ms is not None
                    else None
                )
            outputs.append(AnswerPrediction(qid=qid, status=status, answer_raw=answer))
            totals.append(elapsed)
        metrics = evaluate_answers(references, outputs).model_dump(mode="json")
        cost = _sum_known(teacher_obs[q].cost_micro_usd for q in calls)
        ratio = (
            cost / teacher_all_cost
            if cost is not None and teacher_all_cost is not None and teacher_all_cost > 0
            else None
        )
        coverage = local_kept / len(qids)
        point = {
            "threshold": threshold,
            "metrics": metrics,
            "local_coverage": coverage,
            "fallback_selections": len(calls),
            "external_requests": _sum_known(teacher_obs[q].external_requests for q in calls),
            "image_transmissions": _sum_known(teacher_obs[q].image_transmissions for q in calls),
            "unique_images_selected_for_fallback": len(
                {samples[q].question.document_id for q in calls}
            ),
            "cost_micro_usd": cost,
            "cost_ratio_vs_teacher_all": ratio,
            "unknown_cost_selections": sum(teacher_obs[q].cost_micro_usd is None for q in calls),
            "recorded_stage_sum_p50_ms": percentile(totals, 0.5)
            if all(t is not None for t in totals)
            else None,
            "recorded_stage_sum_p95_ms": percentile(totals, 0.95)
            if all(t is not None for t in totals)
            else None,
            "targets_met": coverage >= plan.target_local_coverage
            and ratio is not None
            and ratio <= plan.target_cost_ratio
            and metrics["strict_nfc_em"]
            >= teacher_raw["strict_nfc_em"] - plan.max_em_gap_to_teacher,
            "paired_em_vs_teacher_all_raw": paired_delta(
                pool,
                references,
                {p.qid: p.answer_raw for p in outputs},
                {o.prediction.qid: o.prediction.answer_raw for o in teacher.observations},
                resamples=resamples,
            ),
        }
        points.append(point)
    for point in points:
        point["pareto_dominated"] = any(
            _dominates(other, point) for other in points if other is not point
        )
    return {
        "protocol": "routing_grid_report_v1",
        "partition": pool.partition,
        "fixture_only": plan.fixture_only,
        "plan_sha256": digest(plan),
        "pool_sha256": digest(pool),
        "profile_sha256": digest(profile),
        "student_sha256": digest(student),
        "teacher_sha256": digest(teacher),
        "ocr_sha256": digest(
            [r.model_dump(mode="json") for r in sorted(ocr, key=lambda r: r.document_id)]
        ),
        "reference_sha256": digest(
            [r.model_dump(mode="json") for r in sorted(references, key=lambda r: r.qid)]
        ),
        "teacher_all_raw": teacher_raw,
        "teacher_all_verified": teacher_verified,
        "teacher_all_cost_micro_usd": teacher_all_cost,
        "cache_regime": teacher.cache_regime,
        "points": points,
        "selected": None,
        "live_execution": False,
        "limitations": [
            "counterfactual replay; no live budget contention, outages or queue model",
            "recorded stage sums exclude verifier/queue overhead; not end-to-end latency",
            "external eligibility is supplied; this plan grants no API permission",
            "unknown usage stays null; zero teacher-all cost makes ratio undefined",
            "scores are rules, not probabilities; no Brier/ECE or calibrated confidence claimed",
        ],
    }


def _sum_known(values):
    values = list(values)
    return sum(values) if all(v is not None for v in values) else None


def _dominates(a, b):
    if a["cost_micro_usd"] is None or b["cost_micro_usd"] is None:
        return False
    left = (a["metrics"]["strict_nfc_em"], a["local_coverage"], -a["cost_micro_usd"])
    right = (b["metrics"]["strict_nfc_em"], b["local_coverage"], -b["cost_micro_usd"])
    return all(x >= y for x, y in zip(left, right, strict=True)) and left != right
