"""Public reporting must reject missing gates, synthetic payloads or changed evidence."""

import json

import pytest
from test_phase4_analysis import comparison  # noqa: F401 -- synthetic CPU fixture

from vidoclens.common.pilot import sha256
from vidoclens.contracts.distillation import Phase4Criteria, Phase4GateReport
from vidoclens.eval.phase4_report import report
from vidoclens.eval.silver_comparison import compare_results
from vidoclens.filtering.io import write_model


@pytest.mark.parametrize("case", ["machine_gate", "changed_file", "unbound_input", "fixture"])
def test_report_cannot_promote_unverified_artifacts_to_results(tmp_path, case):
    execution = tmp_path / "synthetic-execution"
    paths = {}
    values = {
        "pilot_report.json": {"fixture_only": True, "strict": {"n_questions": 666}},
        "labeling/freeze/config.json": {"fixture_only": True},
        "holdout_report.json": {"fixture_only": True},
        "comparison/comparison.json": {"fixture_only": True},
        "train_fit_teacher/manifest.json": {"fixture_only": True},
        "audit_holdout_teacher/manifest.json": {"fixture_only": True},
    }
    for name, value in values.items():
        path = execution / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_model(path, value)
        paths[str(path)] = sha256(path)
    criteria = dict.fromkeys(Phase4Criteria.model_fields.keys() - {"schema_version"}, True)
    criteria["human_error_review"] = False
    if case == "machine_gate":
        criteria["matched_three_seed_training"] = False
    if case == "unbound_input":
        paths.pop(str(execution / "comparison/comparison.json"))
    gate = Phase4GateReport(
        status="incomplete",
        criteria=Phase4Criteria(**criteria),
        evidence=paths,
        h2_primary_difference=0,
        limitations=("synthetic rejection test only",),
    )
    gate_path = tmp_path / "gate.json"
    write_model(gate_path, gate)
    if case == "changed_file":
        (execution / "pilot_report.json").write_text(
            json.dumps({"changed": True}), encoding="utf-8"
        )
    destination = tmp_path / "must-not-exist.md"
    with pytest.raises(ValueError):
        report(tmp_path, execution, gate_path, destination)
    assert not destination.exists()


def test_machine_report_renders_without_claiming_human_gate(comparison, tmp_path):  # noqa: F811
    # Explicit report-boundary stub, only in pytest's temporary directory.
    # No model is loaded and none of these synthetic values are execution evidence.
    train, dev, references, plans, results = comparison
    values = compare_results(train, dev, references, plans, results, resamples=2)
    values["fixture_only"] = False  # stub the already-audited G4 boundary for the formatter
    for row in values["runs"].values():
        row["selected_checkpoint_step"] = 191
    execution = tmp_path / "synthetic-execution"
    data = {
        "pilot_report.json": {
            "generation_mode": "synthetic-test-only",
            "generation_config": {"model_id": "synthetic/test-only", "model_revision": "a" * 40},
            "strict": {
                "n_questions": 666,
                "strict_nfc_em": 0.5,
                "strict_nfc_anls": 0.6,
                "coverage": 1.0,
            },
            "generation_seconds": 1.0,
            "peak_reserved_bytes": 1024,
        },
        "labeling/freeze/config.json": {
            "text_max_normalized_edit_distance": 0,
            "max_consecutive_lines": 3,
        },
        "holdout_report.json": {
            "fixture_only": False,
            "overall": {
                "requested": 2,
                "eligible": 2,
                "kept": 0,
                "filter_precision": None,
                "filter_recall": 0.0,
                "retention": 0.0,
                "false_accept": 0,
                "false_reject": 1,
            },
        },
        "comparison/comparison.json": values,
    }
    for name in ("train_fit", "audit_holdout"):
        data[name + "_teacher/manifest.json"] = {
            "complete": True,
            "fixture_only": False,  # same synthetic, already-audited boundary stub
            "label_status_counts": {"answered": 1},
            "requests": [{"generation_seconds": 1.0, "peak_reserved_bytes": 1024}],
        }
    evidence = {}
    for name, value in data.items():
        path = execution / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_model(path, value)
        evidence[str(path)] = sha256(path)
    criteria = dict.fromkeys(Phase4Criteria.model_fields.keys() - {"schema_version"}, True)
    criteria["human_error_review"] = False
    gate = Phase4GateReport(
        status="incomplete",
        criteria=Phase4Criteria(**criteria),
        evidence=evidence,
        h2_primary_difference=values["paired_em"]["P2_vs_P1-size"]["training_seed_delta_mean"],
        limitations=("synthetic CPU formatter test; not actual evidence",),
    )
    gate_path, output = tmp_path / "synthetic-gate.json", tmp_path / "synthetic-report.md"
    write_model(gate_path, gate)
    result = report(tmp_path, execution, gate_path, output)
    assert result["gate_status"] == "incomplete" and result["sha256"] == sha256(output)
    output.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        report(tmp_path, execution, gate_path, output)
