import hashlib

import pytest
from pydantic import ValidationError

from vidoclens.contracts.ai_review import (
    AIAdjudication,
    AIReviewOutput,
    AIReviewTask,
    OODSeedDocument,
    OODSeedQA,
)
from vidoclens.data.local_ai_review import load_tasks
from vidoclens.data.ood_seed import candidate_reasons, local_file
from vidoclens.data.phase1_gate import require_coverage, validate_review, validate_seed


def document():
    return OODSeedDocument(
        document_id="commons:1:" + "a" * 64,
        page_id=1,
        page_revision=2,
        source_url="https://commons.wikimedia.org/wiki/File:fixture.jpg",
        original_url="https://upload.wikimedia.org/fixture.jpg",
        author_credit="Test fixture",
        license_id="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_evidence_id="commons:1:revision:2",
        metadata_sha256="b" * 64,
        metadata_path="metadata.json",
        raw_path="raw.jpg",
        image_path="fixture.png",
        raw_image_sha256="a" * 64,
        processed_image_sha256="c" * 64,
        canonical_pixel_sha256="d" * 64,
        width=10,
        height=10,
        document_kind="test_fixture",
        shift_axes=("source",),
        source_caveats=(),
        partition="ood_seed",
    )


def annotation():
    doc = document()
    return OODSeedQA(
        qid=doc.document_id + ":question:1",
        document_id=doc.document_id,
        image_sha256=doc.processed_image_sha256,
        rights_evidence_id=doc.rights_evidence_id,
        source_domain="commons.wikimedia.org",
        shift_axes=doc.shift_axes,
        question="Blank field?",
        question_type="blank",
        answerable=False,
        annotator_type="ai",
        annotator="fixture",
        second_review="ai_only",
    )


def task():
    return AIReviewTask(
        task_id="fixture:line:1",
        document_id="fixture",
        image_path="image.png",
        image_sha256="c" * 64,
        kind="ocr_transcription",
        question="Transcribe the visible line.",
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("eligible_as_human_gold", True),
        ("eligible_for_training", True),
        ("eligible_for_confirmatory_evaluation", True),
        ("annotator_type", "human"),
        ("qid", "another-document:question:1"),
    ],
)
def test_ai_seed_cannot_escalate_gold_or_training(key, value):
    with pytest.raises(ValidationError):
        OODSeedQA.model_validate({**annotation().model_dump(), key: value})


@pytest.mark.parametrize("field", ["answer", "full_answers", "reference", "ocr_text"])
def test_reviewer_contract_rejects_label_fields(field):
    with pytest.raises(ValidationError):
        AIReviewTask.model_validate({**task().model_dump(), field: "hidden label"})


def test_seed_binding_pending_quarantine_and_duplicates():
    doc, qa = document(), annotation()
    validate_seed([doc], [qa])
    for changed in (
        qa.model_copy(update={"second_review": "pending"}),
        qa.model_copy(update={"rights_evidence_id": "unbound"}),
        qa.model_copy(update={"image_sha256": "f" * 64}),
    ):
        with pytest.raises(ValueError):
            validate_seed([doc], [changed])
    with pytest.raises(ValueError):
        validate_seed([doc.model_copy(update={"partition": "quarantine"})], [qa])
    with pytest.raises(ValueError):
        validate_seed([doc], [qa, qa])


def test_answerability_requires_evidence_and_preserves_digits():
    qa = annotation().model_dump()
    with pytest.raises(ValidationError):
        OODSeedQA.model_validate({**qa, "answerable": True, "full_answers": ["0078700"]})
    value = OODSeedQA.model_validate(
        {
            **qa,
            "answerable": True,
            "full_answers": ["0078700"],
            "evidence_boxes": [{"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2}],
        }
    )
    assert value.full_answers == ("0078700",)


def test_tasks_verify_image_hash_and_deny_escape(tmp_path):
    payload = b"explicit synthetic test fixture"
    (tmp_path / "image.png").write_bytes(payload)
    sample = task().model_copy(update={"image_sha256": hashlib.sha256(payload).hexdigest()})
    file = tmp_path / "tasks.jsonl"
    file.write_text(sample.model_dump_json() + "\n", encoding="utf-8")
    assert load_tasks(tmp_path, file) == (sample,)
    (tmp_path / "image.png").write_bytes(b"changed")
    with pytest.raises(ValueError):
        load_tasks(tmp_path, file)
    with pytest.raises(ValueError):
        local_file(tmp_path, "../outside.png")


def test_no_automatic_acceptance_of_agreement_or_truncation():
    entry = task()
    result = AIReviewOutput(
        task_id=entry.task_id,
        input_image_sha256=entry.image_sha256,
        raw_text="VISIBLE",
        generated_tokens=2,
        truncated=False,
        status="ok",
        seconds=1,
        peak_allocated_bytes=1,
    )
    final = {entry.task_id: "a" * 64}
    decision = AIAdjudication(
        task_id=entry.task_id,
        reviewer_output_sha256="b" * 64,
        final_record_sha256=final[entry.task_id],
        decision="confirmed_from_image",
        rationale="Synthetic fixture for explicit adjudication requirement",
    )
    with pytest.raises(ValueError):
        validate_review([entry], [result], [], final)
    assert validate_review([entry], [result], [decision], final) == {entry.task_id}
    assert not validate_review(
        [entry], [result.model_copy(update={"truncated": True})], [decision], final
    )
    with pytest.raises(ValueError):
        validate_review([entry], [result], [decision], {entry.task_id: "f" * 64})
    with pytest.raises(ValueError):
        validate_review(
            [entry], [result.model_copy(update={"input_image_sha256": "f" * 64})], [decision], final
        )


def test_insufficient_coverage_cannot_close_gate():
    with pytest.raises(ValueError):
        require_coverage([document()], [annotation()], [], set(), {})


def test_cross_source_exact_and_rotated_candidates_are_not_silently_accepted():
    left = {
        "raw_image_sha256": "a",
        "canonical_pixel_sha256": "b",
        "phash64": "0123456789abcdef",
        "center_crop_phash64": "0123456789abcdef",
        "phash_rotations": ["0123456789abcdef", "fedcba9876543210"],
        "crop60_phash": "0123456789abcdef",
        "gradient_rotations": ["a5" * 16],
    }
    reasons, distances = candidate_reasons(left, left)
    assert {"raw_image_sha256", "canonical_pixel_sha256", "rotation", "gradient"} <= set(reasons)
    assert distances["full"] == 0
    right = {
        **left,
        "raw_image_sha256": "x",
        "canonical_pixel_sha256": "y",
        "phash64": "fedcba9876543210",
        "phash_rotations": ["fedcba9876543210"],
    }
    reasons, _ = candidate_reasons(left, right)
    assert "rotation" in reasons and "raw_image_sha256" not in reasons
