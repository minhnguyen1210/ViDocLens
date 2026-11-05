"""Lossless derived parsing: valid siblings survive; malformed answers never get repaired."""

import json
import sqlite3

import pytest
from test_local_labels import config, grant
from test_silver import pool, sample

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGeneration
from vidoclens.teacher.local_labels import build_plan, parse_generation, run_local
from vidoclens.teacher.reparse import derive, parse_items, run, verify


def request_and_raw():
    p = pool().model_copy(update={"samples": tuple(sample(i, image_id=1) for i in (1, 2, 3))})
    request = build_plan(p, config(qid_format="request_local_v1"), fixture_only=True).requests[0]
    raw = {
        "answers": [
            {
                "qid": "q0",
                "answer": "",
                "answerable": False,
                "evidence_text": None,
                "reason_code": "unreadable",
            },
            {
                "qid": "q1",
                "answer": " 012,50 đ\n",
                "answerable": True,
                "evidence_text": "012,50 đ",
                "reason_code": "visible_text",
            },
            {
                "qid": "q2",
                "answer": None,
                "answerable": False,
                "evidence_text": None,
                "reason_code": "unreadable",
            },
        ]
    }
    return p, request, raw


def test_bad_item_is_not_repaired_and_valid_raw_siblings_survive():
    _, request, raw = request_and_raw()
    generation = LocalGeneration(raw_text=json.dumps(raw, ensure_ascii=False), status="completed")
    assert all(r.status == "parse_error" for r in parse_generation(request, generation))
    parsed = parse_items(request, generation)
    assert [r.status for r in parsed] == ["parse_error", "answered", "unanswerable"]
    assert parsed[1].answer_raw == " 012,50 đ\n" and parsed[0].answer_raw is None
    assert len({r.raw_response_sha256 for r in parsed}) == 1


@pytest.mark.parametrize(
    "mutation", ["duplicate", "unknown", "extra_envelope", "unidentifiable", "fence"]
)
def test_ambiguous_envelope_still_rejects_entire_request(mutation):
    _, request, raw = request_and_raw()
    if mutation == "duplicate":
        raw["answers"][0]["qid"] = "q1"
    elif mutation == "unknown":
        raw["answers"][0]["qid"] = "q999"
    elif mutation == "extra_envelope":
        raw["guessed"] = True
    elif mutation == "unidentifiable":
        raw["answers"][0].pop("qid")
    text = json.dumps(raw)
    if mutation == "fence":
        text = "```json\n" + text + "\n```"
    assert all(
        r.status == "parse_error"
        for r in parse_items(request, LocalGeneration(raw_text=text, status="completed"))
    )


def test_completed_cache_derivation_replay_and_tamper_detection(tmp_path):
    p, _, raw = request_and_raw()
    image = tmp_path / "synthetic.bin"
    image.write_bytes(b"synthetic fixture image")
    p = p.model_copy(
        update={
            "samples": tuple(
                s.model_copy(update={"image_sha256": sha256(image)}) for s in p.samples
            )
        }
    )
    plan = build_plan(p, config(qid_format="request_local_v1"), fixture_only=True)

    class FixtureBackend:
        fixture_only = True

        def generate(self, request, image):
            return LocalGeneration(raw_text=json.dumps(raw), status="completed")

    source = tmp_path / "original"
    original, _ = run_local(
        p,
        plan,
        grant(plan),
        FixtureBackend(),
        {p.samples[0].question.document_id: image},
        {"fixture_only": True},
        source,
        run_id="synthetic-only",
    )
    source_hash = sha256(source / "manifest.json")
    parsed, report = run(source, tmp_path / "parsed")
    assert report.new_model_calls == 0 and report.raw_answers_modified is False
    assert report.fixture_only and parsed.fixture_only
    assert original.labels[1].status == "parse_error" and parsed.labels[1].status == "answered"
    assert sha256(source / "manifest.json") == source_hash
    assert verify(source, tmp_path / "parsed")[0] == parsed
    with sqlite3.connect(source / "attempts.sqlite") as db:
        db.execute("UPDATE attempts SET checksum=?", ("b" * 64,))
    with pytest.raises(ValueError, match="checksum"):
        derive(source)
