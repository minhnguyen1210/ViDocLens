"""No model imports/downloads: test the real orchestration with a fixture backend."""

import json
import sqlite3

import pytest
from test_silver import HASH, frozen, pool, sample

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import (
    LocalGeneration,
    LocalGenerationGrant,
    LocalModelSnapshot,
    LocalTeacherConfig,
)
from vidoclens.filtering.io import digest, write_model
from vidoclens.teacher.local_labels import build_plan, parse_generation, request_text, run_local
from vidoclens.teacher.local_qwen import snapshot_files, validate_snapshot


def config(**updates):
    return LocalTeacherConfig(
        model_id="synthetic/local",
        model_revision="b" * 40,
        snapshot_manifest_sha256=HASH,
        **updates,
    )


def grant(plan):
    return LocalGenerationGrant(
        plan_sha256=digest(plan),
        purpose="silver_generation",
        generation_allowed=True,
        data_rights_verified=True,
        model_license_verified=True,
        quality_pilot_passed=True,
        evidence_sha256=HASH,
        approved_by="synthetic-test-only",
    )


def response(request, **updates):
    raw = json.dumps(
        {
            "answers": [
                {
                    "qid": q.qid,
                    "answer": "001,50 đ",
                    "evidence_text": "001,50 đ",
                    "answerable": True,
                    "reason_code": "visible_text",
                }
                for q in request.questions
            ]
        },
        ensure_ascii=False,
    )
    return LocalGeneration(raw_text=raw, status="completed", **updates)


class Backend:
    fixture_only = True

    def __init__(self):
        self.calls = []

    def generate(self, request, image):
        assert image.is_file()
        self.calls.append(request)
        return response(request)


@pytest.fixture
def inputs(tmp_path):
    p = pool(2)
    images, samples = {}, []
    for index, s in enumerate(p.samples):
        path = tmp_path / f"{index}.png"
        path.write_bytes(b"synthetic image bytes " + str(index).encode())
        images[s.question.document_id] = path
        samples.append(s.model_copy(update={"image_sha256": sha256(path)}))
    p = p.model_copy(update={"samples": tuple(samples)})
    plan = build_plan(p, config(), fixture_only=True)
    return p, plan, grant(plan), images


def execute(inputs, backend, output, **kwargs):
    p, plan, permission, images = inputs
    return run_local(
        p, plan, permission, backend, images, {"fixture": True}, output, run_id="test", **kwargs
    )


def test_deterministic_chunking_and_question_only():
    p = pool().model_copy(update={"samples": tuple(sample(i, image_id=1) for i in range(1, 6))})
    plan = build_plan(p, config(max_questions=2), fixture_only=True)
    reordered = p.model_copy(update={"samples": tuple(reversed(p.samples))})
    other = build_plan(reordered, config(max_questions=2), fixture_only=True)
    assert [len(r.questions) for r in plan.requests] == [2, 2, 1]
    assert plan.requests == other.requests
    assert all(r.document_id == p.samples[0].question.document_id for r in plan.requests)
    text = request_text(plan.requests[0], plan.config)
    assert "gold" not in text.lower() and "GOLD_MUST" not in plan.model_dump_json()
    assert p.gold_samples[0].question.qid not in plan.model_dump_json()
    with pytest.raises(ValueError, match="character cap"):
        build_plan(p, config(max_question_characters=128))


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("missing", "missing_qid"),
        ("duplicate", "invalid_output_schema_or_qids"),
        ("unknown", "invalid_output_schema_or_qids"),
        ("contradiction", "invalid_output_schema_or_qids"),
        ("extra", "invalid_output_schema_or_qids"),
        ("fenced", "invalid_output_schema_or_qids"),
    ],
)
def test_parser_malformed_outputs(mutation, expected):
    request = build_plan(pool(), config()).requests[0]
    raw = json.loads(response(request).raw_text)
    if mutation == "missing":
        raw["answers"] = []
    elif mutation == "duplicate":
        raw["answers"] *= 2
    elif mutation == "unknown":
        raw["answers"][0]["qid"] = "unknown"
    elif mutation == "contradiction":
        raw["answers"][0]["answerable"] = False
    elif mutation == "extra":
        raw["answers"][0]["reference"] = "forbidden"
    text = json.dumps(raw)
    if mutation == "fenced":
        text = "```json\n" + text + "\n```"
    labels = parse_generation(request, LocalGeneration(raw_text=text, status="completed"))
    assert labels[0].status == "parse_error" and labels[0].reason == expected
    assert labels[0].answer_raw is None


def test_parser_raw_null_and_truncation():
    request = build_plan(pool(), config()).requests[0]
    assert parse_generation(request, response(request))[0].answer_raw == "001,50 đ"
    raw = json.loads(response(request).raw_text)
    raw["answers"][0].update(answer=None, answerable=False, reason_code="unreadable")
    assert (
        parse_generation(request, LocalGeneration(raw_text=json.dumps(raw), status="completed"))[
            0
        ].status
        == "unanswerable"
    )
    assert (
        parse_generation(request, response(request).model_copy(update={"status": "incomplete"}))[
            0
        ].status
        == "incomplete"
    )


def test_complete_replay_zero_new_calls_and_raw_provenance(inputs, tmp_path):
    backend = Backend()
    batch, result = execute(inputs, backend, tmp_path / "run")
    assert result["new_calls"] == 2 and len(batch.labels) == 2
    again, replay = execute(inputs, backend, tmp_path / "run", max_attempts=3)
    assert replay["new_calls"] == 0 and batch == again and len(backend.calls) == 2
    with sqlite3.connect(tmp_path / "run" / "attempts.sqlite") as db:
        rows = db.execute("SELECT generation FROM attempts").fetchall()
    assert len(rows) == 2 and all("001,50" in row[0] for row in rows)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["quality_measured"] is False and manifest["training_approved"] is False


def test_crash_resume_only_unfinished_request(inputs, tmp_path):
    class Interrupted(Backend):
        def generate(self, request, image):
            if self.calls:
                raise KeyboardInterrupt()
            return super().generate(request, image)

    out = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        execute(inputs, Interrupted(), out)
    assert not (out / "manifest.json").exists() and not (out / "run.lock").exists()
    backend = Backend()
    _, result = execute(inputs, backend, out)
    assert result["new_calls"] == 1 and len(backend.calls) == 1


def test_retry_bounded_errors_not_success(inputs, tmp_path):
    class Broken(Backend):
        def generate(self, request, image):
            self.calls.append(request)
            raise RuntimeError("PRIVATE_CONTENT_NOT_FOR_LOG")

    backend = Broken()
    batch, result = execute(inputs, backend, tmp_path / "run", max_attempts=2)
    assert result["new_calls"] == 4 and all(r.status == "error" for r in batch.labels)
    assert b"PRIVATE_CONTENT" not in (tmp_path / "run" / "attempts.sqlite").read_bytes()
    _, replay = execute(inputs, backend, tmp_path / "run", max_attempts=3)
    assert replay["new_calls"] == 0  # Complete failure reports are immutable too.


@pytest.mark.parametrize(
    "change", ["permission", "fixture", "image", "plan", "environment", "cache", "metadata", "lock"]
)
def test_fail_closed_before_new_inference(inputs, tmp_path, change):
    p, plan, permission, images = inputs
    backend, out = Backend(), tmp_path / "run"
    if change in {"environment", "cache", "metadata"}:
        execute(inputs, backend, out)
        backend.calls.clear()
    if change == "permission":
        inputs = (p, plan, permission.model_copy(update={"model_license_verified": False}), images)
    elif change == "fixture":
        backend.fixture_only = False
    elif change == "image":
        next(iter(images.values())).write_bytes(b"different")
    elif change == "plan":
        inputs = (p, plan.model_copy(update={"prompt_sha256": "c" * 64}), permission, images)
    elif change == "environment":
        with pytest.raises(ValueError, match="resume binding"):
            run_local(p, plan, permission, backend, images, {"changed": True}, out, run_id="test")
        assert not backend.calls
        return
    elif change == "cache":
        with sqlite3.connect(out / "attempts.sqlite") as db:
            db.execute("UPDATE attempts SET checksum=?", ("c" * 64,))
    elif change == "metadata":
        (out / "batch.json").write_text("{}")
    elif change == "lock":
        out.mkdir()
        (out / "run.lock").write_text("active")
    with pytest.raises((ValueError, PermissionError, FileExistsError)):
        execute(inputs, backend, out)
    assert not backend.calls


def test_quality_pilot_cannot_generate_training_labels(inputs, tmp_path):
    p, plan, permission, images = inputs
    permission = permission.model_copy(
        update={"purpose": "quality_pilot", "quality_pilot_passed": False}
    )
    with pytest.raises(PermissionError, match="dev_select"):
        execute((p, plan, permission, images), Backend(), tmp_path / "run")


def test_snapshot_identity_and_file_tamper(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    (root / "config.json").write_text("{}")
    (root / "model.safetensors").write_bytes(b"synthetic-only-not-a-model")
    path = tmp_path / "snapshot.json"
    write_model(
        path,
        LocalModelSnapshot(
            model_id="synthetic/local", model_revision="b" * 40, files=snapshot_files(root)
        ),
    )
    cfg = config().model_copy(update={"snapshot_manifest_sha256": sha256(path)})
    validate_snapshot(root, path, cfg)
    (root / "config.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="content mismatch"):
        validate_snapshot(root, path, cfg)
    (root / ".env").write_text("synthetic only")
    with pytest.raises(ValueError, match="unexpected file"):
        snapshot_files(root)


def test_duplicate_json_keys_rejected():
    request = build_plan(pool(), config()).requests[0]
    output = response(request).raw_text
    duplicate = '{"answers": [], ' + output[1:]
    result = parse_generation(request, LocalGeneration(raw_text=duplicate, status="completed"))
    assert result[0].status == "parse_error"


@pytest.mark.parametrize("freeze", [None, "wrong_access", "valid"])
def test_holdout_generation_requires_frozen_matching_rules(inputs, tmp_path, freeze):
    p, _, _, images = inputs
    p = p.model_copy(update={"partition": "audit_holdout", "gold_samples": ()})
    plan = build_plan(p, config(), fixture_only=True)
    settings = frozen() if freeze else None
    if freeze == "wrong_access":
        settings = settings.model_copy(update={"freeze_access_plan_sha256": "c" * 64})
    backend = Backend()
    if freeze == "valid":
        result, _ = execute(
            (p, plan, grant(plan), images), backend, tmp_path / "run", frozen_filter=settings
        )
        assert len(result.labels) == 2
    else:
        with pytest.raises(PermissionError, match="frozen"):
            execute(
                (p, plan, grant(plan), images), backend, tmp_path / "run", frozen_filter=settings
            )
        assert not backend.calls


def test_silver_generation_denied_without_quality_gate(inputs, tmp_path):
    p, plan, permission, images = inputs
    permission = permission.model_copy(update={"quality_pilot_passed": False})
    backend = Backend()
    with pytest.raises(PermissionError, match="quality pilot"):
        execute((p, plan, permission, images), backend, tmp_path / "run")
    assert not backend.calls
