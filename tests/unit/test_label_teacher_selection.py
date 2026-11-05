"""Teacher selection cannot bypass quality gates, cohort identity or frozen report bytes."""

from copy import deepcopy

import pytest

from vidoclens.distillation.inputs import COHORT_SHA256, G3_EVIDENCE_SHA256
from vidoclens.eval.label_teacher_selection import CRITERIA, choose, run, verify_selection
from vidoclens.filtering.io import write_model


def reports():
    common = {
        "pool_sha256": "a" * 64,
        "cohort_sha256": COHORT_SHA256,
        "g3_sha256": G3_EVIDENCE_SHA256,
        "status": "pass",
        "zero_call_replay": True,
        "criteria": dict.fromkeys(CRITERIA, True),
        "strict": {"n_questions": 666, "strict_nfc_em": 0.4, "strict_nfc_anls": 0.6},
        "generation_seconds": 100,
    }
    return [
        deepcopy(common) | {"generation_mode": mode, "source_run": "runs/" + mode}
        for mode in ("raw_single_v1", "structured_batch_v1")
    ]


def test_eligibility_precedes_metric_ranking_and_no_eligible_is_failure():
    candidates = reports()
    candidates[0]["strict"]["strict_nfc_em"] = 0.5
    candidates[0]["criteria"]["actual_gpu_measurements"] = False
    candidates[0]["status"] = "fail"
    assert choose(candidates) is candidates[1]
    candidates[1]["criteria"]["no_inference_errors"] = False
    candidates[1]["status"] = "fail"
    assert choose(candidates) is None


def test_selection_metric_ties_use_preregistered_order():
    candidates = reports()
    candidates[0]["generation_seconds"] = 200
    assert choose(candidates) is candidates[1]
    candidates[0]["strict"]["strict_nfc_anls"] = 0.61
    assert choose(candidates) is candidates[0]
    candidates[1]["strict"]["strict_nfc_em"] = 0.41
    assert choose(candidates) is candidates[1]


@pytest.mark.parametrize("mutation", ["cohort", "partial", "empty_criteria", "missing_candidate"])
def test_incomparable_candidates_cannot_select(mutation):
    candidates = reports()
    if mutation == "cohort":
        candidates[0]["cohort_sha256"] = "c" * 64
    elif mutation == "partial":
        candidates[0]["strict"]["n_questions"] = 665
    elif mutation == "empty_criteria":
        candidates[0]["criteria"] = {}
    else:
        candidates.pop()
    with pytest.raises(ValueError):
        choose(candidates)


def test_execution_rejects_changed_report_or_nonselected_mode(tmp_path):
    candidates = reports()
    candidates[0]["strict"]["strict_nfc_em"] = 0.5
    paths = [tmp_path / f"report-{i}.json" for i in range(2)]
    for path, value in zip(paths, candidates, strict=True):
        write_model(path, value)
    selection = tmp_path / "selection.json"
    run(paths, selection)
    pilot = tmp_path / candidates[0]["source_run"]
    assert verify_selection(tmp_path, selection, pilot, True) == candidates[0]
    with pytest.raises(ValueError, match="not the preregistered selected"):
        verify_selection(tmp_path, selection, pilot, False)
    paths[1].write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after selection"):
        verify_selection(tmp_path, selection, pilot, True)
