import pytest
from pydantic import ValidationError

from vidoclens.contracts.models import (
    Box,
    Prediction,
    Provenance,
    QARecord,
    TeacherInput,
    TeacherLabel,
)


@pytest.fixture
def provenance():
    return Provenance(
        run_id="synthetic-run",
        document_id="doc-1",
        qid="q-1",
        question="Tổng tiền?",
        model_id="test-only",
        model_revision="none",
        prompt_hash="test",
        config_hash="test",
    )


@pytest.mark.parametrize("answer", [None, "", " \t\n "])
def test_prediction_cannot_claim_answered_without_answer(provenance, answer):
    with pytest.raises(ValidationError, match="nonempty raw answer"):
        Prediction(status="answered", answer_raw=answer, backend="local", provenance=provenance)


@pytest.mark.parametrize("status", ["abstained", "error"])
@pytest.mark.parametrize("answer_field", ["answer_raw", "answer_normalized"])
def test_unanswered_prediction_cannot_leak_answer(provenance, status, answer_field):
    with pytest.raises(ValidationError, match="must not contain an answer"):
        Prediction(
            status=status,
            reason="unreadable",
            backend="local",
            provenance=provenance,
            **{answer_field: "125.000"},
        )


def test_unlabeled_record_cannot_carry_hidden_gold():
    with pytest.raises(ValidationError, match="unlabeled records"):
        QARecord(
            qid="q-1",
            document_id="doc-1",
            question="Tổng tiền?",
            label_source="unlabeled",
            answers=["125.000"],
        )


def test_teacher_input_rejects_nested_answer_fields():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TeacherInput.model_validate(
            {
                "document_id": "doc-1",
                "image_sha256": "a" * 64,
                "questions": [{"qid": "q-1", "question": "Tổng tiền?", "answer": "125.000"}],
            }
        )


def test_full_reference_alternatives_keep_separate_evidence_parts():
    record = QARecord.model_validate(
        {
            "qid": "q-1",
            "document_id": "doc-1",
            "question": "Các mặt hàng là gì?",
            "label_source": "gold",
            "answers": ["Cà phê ¡sep¿ Trà", "CA PHE ¡sep¿ TRA"],
            "answer_parts": [
                [
                    {"text": "Cà phê", "evidence": {"span_ids": ["line-1"]}},
                    {"text": "Trà", "evidence": {"span_ids": ["line-2"]}},
                ],
                [{"text": "CA PHE"}, {"text": "TRA"}],
            ],
        }
    )
    assert record.answers[0] == "Cà phê ¡sep¿ Trà"
    assert record.answer_parts[0][1].evidence.span_ids == ["line-2"]
    assert len(record.answers) == len(record.answer_parts) == 2


def test_teacher_abstention_cannot_carry_an_answer():
    with pytest.raises(ValidationError, match="must have answer=null"):
        TeacherLabel(
            qid="q-1",
            answer="125.000",
            evidence_text=None,
            answerable=False,
            reason_code="unreadable",
        )


def test_evidence_box_cannot_reverse_coordinates():
    with pytest.raises(ValidationError, match="positive width"):
        Box(x0=0.9, y0=0, x1=0.1, y1=1)
