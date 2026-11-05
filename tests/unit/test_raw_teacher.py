"""Single-QA raw candidate preserves actual text and exact-plan replay boundaries."""

import pytest
from test_local_labels import grant
from test_silver import HASH, pool

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGeneration
from vidoclens.contracts.raw_teacher import RawTeacherConfig
from vidoclens.teacher.raw_labels import build_plan, parse_generation, request_text, run_local


def config():
    return RawTeacherConfig(
        model_id="synthetic/raw", model_revision="b" * 40, snapshot_manifest_sha256=HASH
    )


@pytest.mark.parametrize(
    "raw,status,answer",
    [
        (" 001,50 đ\n", "answered", " 001,50 đ\n"),
        ("<unanswerable>\n", "unanswerable", None),
        (" \n", "parse_error", None),
        ('{"answer":"125"}', "answered", '{"answer":"125"}'),
    ],
)
def test_raw_answers_are_not_stripped_parsed_or_corrected(raw, status, answer):
    plan = build_plan(pool(), config(), fixture_only=True)
    request = plan.requests[0]
    assert len(request.questions) == 1 and request.questions[0].qid not in request_text(request)
    labels = parse_generation(request, LocalGeneration(raw_text=raw, status="completed"))
    assert labels[0].status == status and labels[0].answer_raw == answer
    assert labels[0].evidence_text is None
    assert (
        parse_generation(request, LocalGeneration(raw_text=raw, status="incomplete"))[0].answer_raw
        is None
    )


def test_raw_complete_zero_call_replay_and_changed_plan_rejected(tmp_path):
    p = pool()
    image = tmp_path / "fixture.bin"
    image.write_bytes(b"fixture-only")
    p = p.model_copy(
        update={
            "samples": tuple(
                s.model_copy(update={"image_sha256": sha256(image)}) for s in p.samples
            )
        }
    )
    plan = build_plan(p, config(), fixture_only=True)
    images = {p.samples[0].question.document_id: image}

    class Backend:
        fixture_only = True
        calls = 0

        def generate(self, request, image):
            self.calls += 1
            return LocalGeneration(raw_text="001,50 đ", status="completed")

    backend = Backend()
    args = (p, plan, grant(plan), backend, images, {"fixture_only": True}, tmp_path / "run")
    batch, first = run_local(*args, run_id="synthetic-raw")
    replay, second = run_local(*args, run_id="synthetic-raw")
    assert batch == replay and backend.calls == first["new_calls"] == 1 and second["new_calls"] == 0
    from vidoclens.teacher.raw_replay import replay_run

    assert replay_run(tmp_path / "run", p, images) == batch
    altered = config().model_copy(update={"max_new_tokens": 64})
    other = build_plan(p, altered, fixture_only=True)
    with pytest.raises(ValueError, match="binding"):
        run_local(
            p,
            other,
            grant(other),
            backend,
            images,
            {"fixture_only": True},
            tmp_path / "run",
            run_id="synthetic-raw",
        )
    import sqlite3

    with sqlite3.connect(tmp_path / "run/attempts.sqlite") as cache:
        cache.execute("DELETE FROM attempts")
    with pytest.raises(ValueError, match="missing attempts"):
        replay_run(tmp_path / "run", p, images)
    assert backend.calls == 1
