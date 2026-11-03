import json

import pytest

from vidoclens.eval.phase2 import read_run, select_roles


@pytest.fixture
def candidates():
    metrics = {
        name: {"strict": {"strict_nfc_em": score, "strict_nfc_anls": score, "n_questions": 100}}
        for name, score in {"A1": 0.8, "A2": 0.9, "A3": 0.85, "A5": 0.88}.items()
    }
    operations = {name: {"spent_usd": 0.1 if name == "A5" else 1.0} for name in metrics}
    policy = {
        "benchmark_candidates": ["A1", "A2", "A3", "A5"],
        "fallback_strong_candidates": ["A2", "A3"],
        "fallback_cheap_candidate": "A5",
        "fallback_max_em_drop": 0.02,
        "label_strategy": "local_candidate_pending_pilot",
    }
    return metrics, operations, policy


def test_fallback_two_point_boundary_and_cost(candidates):
    metrics, operations, policy = candidates
    selected = select_roles(metrics, operations, policy)
    assert selected["benchmark_experiment"] == "A2"
    assert selected["fallback_experiment"] == "A5"
    assert not selected["api_training_export_allowed"]
    operations["A5"]["spent_usd"] = 1
    assert select_roles(metrics, operations, policy)["fallback_experiment"] == "A2"


def test_cheaper_fallback_rejected_when_accuracy_gap_too_large(candidates):
    metrics, operations, policy = candidates
    metrics["A5"]["strict"]["strict_nfc_em"] = 0.87
    assert select_roles(metrics, operations, policy)["fallback_experiment"] == "A2"


def test_benchmark_quality_then_anls_then_cost(candidates):
    metrics, operations, policy = candidates
    metrics["A5"]["strict"]["strict_nfc_em"] = 0.9
    assert select_roles(metrics, operations, policy)["benchmark_experiment"] == "A2"
    metrics["A5"]["strict"]["strict_nfc_anls"] = 0.9
    assert select_roles(metrics, operations, policy)["benchmark_experiment"] == "A5"
    metrics.pop("A1")
    with pytest.raises(ValueError):
        select_roles(metrics, operations, policy)


def test_finalization_rejects_incomplete_run(tmp_path):
    report = {
        "source": "openai_responses",
        "plan_sha256": "a" * 64,
        "complete": False,
        "expected": 1,
        "files": {},
    }
    (tmp_path / "run.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        read_run(tmp_path, {"b" * 64}, "a" * 64)
