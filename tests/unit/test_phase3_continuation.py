import json

import pytest
from pydantic import ValidationError

from vidoclens.common.pilot import sha256
from vidoclens.contracts.phase3 import Phase3Continuation, Phase3EvidenceFile
from vidoclens.contracts.student import StudentConfig
from vidoclens.eval.continuation import (
    expected_runs,
    file_reference,
    resolve,
    run_reference,
)
from vidoclens.eval.phase3 import verify_profile, verify_sources, verify_training_config


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path
    parent, fresh = root / "parent", root / "fresh"
    parent.mkdir()
    fresh.mkdir()
    expected = expected_runs((17, 42, 2026), 191)
    plan_hash = "a" * 64
    runs, partial, parent_steps, fresh_steps = {}, {}, [], []

    def execute(directory, steps, module, flag, destination, code=0):
        log = directory / f"step_{len(steps)}.log"
        log.write_text("synthetic execution fixture")
        steps.append(
            {
                "command": ["python", "-m", module, flag, destination.relative_to(root).as_posix()],
                "exit_code": code,
                "log": log.name,
                "log_sha256": sha256(log),
            }
        )

    def make_run(directory, kind, complete=True):
        put(
            directory / "run.json",
            {
                "complete": complete,
                "error": None,
                "plan_sha256": plan_hash,
                "completed": 2 if complete else 1,
                "expected": 2,
            },
        )
        put(directory / "profile.json", {})
        if kind == "prediction":
            put(directory / "predictions.jsonl", {"synthetic": True})
            if complete:
                put(directory / "metrics.json", {})
        else:
            for name in ["config.json", "learning_curve.jsonl", "reload_probe.json"]:
                put(directory / name, {})

    for label, kind in expected.items():
        new = label in {"L2_seed2026_step96", "L2_seed2026_step191"}
        directory = (fresh if new else parent) / label
        make_run(directory, kind)
        runs[label] = run_reference(root, directory, kind)
        steps = fresh_steps if new else parent_steps
        execute(
            directory.parent,
            steps,
            "vidoclens.student.train" if kind == "training" else "vidoclens.student.predict",
            "--output",
            directory,
        )
        if kind == "prediction":
            execute(directory.parent, steps, "vidoclens.eval.student", "--run-dir", directory)
    interrupted = "L2_seed2026_step96"
    old = parent / interrupted
    make_run(old, "prediction", complete=False)
    value = json.loads((old / "run.json").read_text())
    value["predictions_sha256"] = sha256(old / "predictions.jsonl")
    put(old / "run.json", value)
    partial[interrupted] = run_reference(root, old, "prediction", partial=True)
    execute(parent, parent_steps, "vidoclens.student.predict", "--output", old, -2)
    put(
        parent / "campaign.json",
        {"complete": False, "plan_sha256": plan_hash, "steps": parent_steps},
    )
    put(
        root / "pause.json",
        {
            "reason": "explicit_user_requested_pause",
            "campaign": "parent/campaign.json",
            "campaign_sha256": sha256(parent / "campaign.json"),
            "interrupted_evaluation": {"name": interrupted, "completed": 1, "expected": 2},
            "partial_run_sha256": sha256(old / "run.json"),
            "partial_predictions_sha256": sha256(old / "predictions.jsonl"),
        },
    )
    (fresh / "execute.py").write_text("# synthetic runner fixture")
    put(
        fresh / "execution.json",
        {
            "complete": True,
            "error": None,
            "steps": fresh_steps,
            "parent_sha256": sha256(parent / "campaign.json"),
            "parent_campaign": "parent/campaign.json",
            "script_sha256": sha256(fresh / "execute.py"),
        },
    )
    manifest = Phase3Continuation(
        plan_sha256=plan_hash,
        parent_campaign=file_reference(root, parent / "campaign.json"),
        execution=file_reference(root, fresh / "execution.json"),
        pause_event=file_reference(root, root / "pause.json"),
        runs=runs,
        replaced_incomplete_runs=partial,
    )
    return root, manifest, expected, plan_hash


def test_adoption_preserves_failed_history_and_reuses_completed_runs(evidence):
    root, manifest, expected, digest = evidence
    before = sha256(root / "parent/campaign.json")
    parent, directories = resolve(root, manifest, expected, digest)
    assert not parent["complete"] and parent["steps"][-1]["exit_code"] == -2
    assert len(directories) == 10
    assert directories["L2_seed17"] == root / "parent/L2_seed17"
    assert directories["L2_seed2026_step96"] == root / "fresh/L2_seed2026_step96"
    assert sha256(root / "parent/campaign.json") == before


@pytest.mark.parametrize("path", ["../secret", "/absolute", "C:/Windows", "a\\b", "a/../b", "a//b"])
def test_contract_rejects_noncanonical_paths(path):
    with pytest.raises(ValidationError):
        Phase3EvidenceFile(path=path, sha256="a" * 64)


@pytest.mark.parametrize(
    "relative",
    [
        "parent/campaign.json",
        "parent/step_0.log",
        "fresh/execute.py",
        "parent/L2_seed2026_step96/predictions.jsonl",
        "fresh/L2_seed2026_step96/metrics.json",
    ],
)
def test_changed_evidence_fails_closed(evidence, relative):
    root, manifest, expected, digest = evidence
    (root / relative).write_text("changed")
    with pytest.raises(ValueError):
        resolve(root, manifest, expected, digest)


def test_rejects_cross_plan_and_missing_seed(evidence):
    root, manifest, expected, digest = evidence
    with pytest.raises(ValueError, match="population mismatch"):
        resolve(root, manifest, expected, "b" * 64)
    with pytest.raises(ValueError, match="population mismatch"):
        resolve(
            root,
            manifest.model_copy(update={"runs": {"L1": manifest.runs["L1"]}}),
            expected,
            digest,
        )


def test_rejects_replacement_of_completed_parent_run(evidence):
    root, manifest, expected, digest = evidence
    runs = dict(manifest.runs)
    runs["L1"] = runs["L1"].model_copy(update={"directory": "fresh/L1"})
    with pytest.raises(ValueError, match="replace a completed"):
        resolve(root, manifest.model_copy(update={"runs": runs}), expected, digest)


@pytest.mark.parametrize("complete", [False, True])
def test_partial_or_cross_plan_fresh_run_cannot_be_adopted(evidence, complete):
    root, manifest, expected, digest = evidence
    label = "L2_seed2026_step96"
    directory = root / manifest.runs[label].directory
    value = json.loads((directory / "run.json").read_text())
    value.update(complete=complete, plan_sha256="b" * 64 if complete else digest)
    put(directory / "run.json", value)
    runs = dict(manifest.runs)
    runs[label] = run_reference(root, directory, "prediction")
    with pytest.raises(ValueError, match="incomplete or cross-plan"):
        resolve(root, manifest.model_copy(update={"runs": runs}), expected, digest)


def test_failed_continuation_execution_rejected_even_with_complete_outputs(evidence):
    root, manifest, expected, digest = evidence
    path = root / manifest.execution.path
    value = json.loads(path.read_text())
    value["steps"][-1]["exit_code"] = 1
    put(path, value)
    manifest = manifest.model_copy(update={"execution": file_reference(root, path)})
    with pytest.raises(ValueError, match="failed continuation"):
        resolve(root, manifest, expected, digest)


def test_source_and_runtime_drift_are_rejected(tmp_path):
    directory = tmp_path / "src/vidoclens/student"
    directory.mkdir(parents=True)
    path = directory / "runtime.py"
    path.write_text("# frozen fixture")
    run = {"source_hashes": {"runtime.py": sha256(path)}}
    verify_sources(tmp_path, run)
    path.write_text("# drift")
    with pytest.raises(ValueError, match="source changed"):
        verify_sources(tmp_path, run)
    config = StudentConfig(
        protocol="phase3_gold_v2", attention_backend="math", deterministic_algorithms=True
    )
    profile = {
        "model_id": config.model_id,
        "revision": config.revision,
        "weights_sha256": config.weights_sha256,
        "attention_backend": "math",
        "deterministic_algorithms": True,
    }
    verify_profile(profile, config)
    profile["attention_backend"] = "auto"
    with pytest.raises(ValueError, match="profile differs"):
        verify_profile(profile, config)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_training_config_preserves_values_across_platform_newlines(tmp_path, newline):
    config = StudentConfig()
    text = config.model_dump_json(indent=2)
    path = tmp_path / "config.json"
    path.write_bytes(text.replace("\n", newline).encode())
    verify_training_config(tmp_path, config)
    changed = config.model_dump()
    changed["learning_rate"] = config.learning_rate / 2
    put(path, changed)
    with pytest.raises(ValueError, match="configuration changed"):
        verify_training_config(tmp_path, config)
