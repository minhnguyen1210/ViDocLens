"""Offline Phase 2 evaluation. This module cannot call providers or alter prompts."""

from collections import Counter, defaultdict

from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.teacher import TeacherResult
from vidoclens.eval.compatible import PROTOCOL, compatible_scores
from vidoclens.eval.metrics import evaluate_answers
from vidoclens.teacher.requests import request_key


def evaluate_teacher(requests, results, references, prompt):
    expected = {request_key(r, prompt): r for r in requests}
    if len(expected) != len(requests):
        raise ValueError("duplicate evaluation request")
    by_key = {}
    for result in results:
        result = TeacherResult.model_validate(result.model_dump())
        if result.request_key in by_key or result.request_key not in expected:
            raise ValueError("unknown/duplicate result key")
        by_key[result.request_key] = result
    gold = {}
    for reference in references:
        if reference.qid in gold:
            raise ValueError("duplicate gold qid")
        gold[reference.qid] = reference
    grouped = defaultdict(list)
    for request in requests:
        if request.purpose == "dev_baseline" and request.partition == "dev_select":
            grouped[request.experiment].append(request)
        elif request.purpose != "integration_pilot":
            raise PermissionError("Phase 2 selection excludes non-dev evaluation")
    metrics = {}
    common_population = None
    for experiment, rows in grouped.items():
        qids = [q.qid for r in rows for q in r.questions]
        if len(qids) != len(set(qids)) or not set(qids) <= gold.keys():
            raise ValueError("evaluation qid mapping invalid")
        if common_population is not None and common_population != set(qids):
            raise ValueError("baseline populations differ")
        common_population = set(qids)
        predictions, statuses = [], Counter()
        for request in rows:
            result = by_key.get(request_key(request, prompt))
            if result is None:
                statuses["missing"] += 1
                continue
            statuses[result.status] += 1
            if result.status == "ok":
                labels = {x.qid: x for x in result.labels}
                if len(labels) != len(result.labels) or set(labels) != {
                    q.qid for q in request.questions
                }:
                    raise ValueError("cached label/qid mismatch")
                predictions.extend(
                    AnswerPrediction(
                        qid=q.qid,
                        status="answered" if labels[q.qid].answerable else "abstained",
                        answer_raw=labels[q.qid].answer,
                    )
                    for q in request.questions
                )
            else:
                predictions.extend(
                    AnswerPrediction(qid=q.qid, status="error") for q in request.questions
                )
        refs = [gold[q] for q in qids]
        strict = evaluate_answers(refs, predictions).model_dump()
        prediction_map = {p.qid: p.answer_raw for p in predictions}
        compatible = Counter()
        for reference in refs:
            compatible.update(
                compatible_scores(prediction_map.get(reference.qid), reference.answers)
            )
        metrics[experiment] = {
            "strict": strict,
            "compatible_protocol": PROTOCOL,
            "compatible": {k: v / len(refs) for k, v in compatible.items()},
            "images": len({r.document_id for r in rows}),
            "request_statuses": dict(statuses),
            "missing_requests": len(rows)
            - sum(k in by_key for k in (request_key(r, prompt) for r in rows)),
        }
    return {
        "partition": "dev_select",
        "metrics": metrics,
        "results_present": len(by_key),
        "requests_expected": len(requests),
        "role_selection_frozen": False,
        "test_or_ood_used": False,
    }
