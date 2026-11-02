import unicodedata

import pytest
from pydantic import ValidationError

from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction, EvaluationSummary
from vidoclens.eval.metrics import anls, evaluate_answers, exact_match, score_answer, token_f1


@pytest.mark.parametrize("function", [exact_match, token_f1, anls])
def test_nfc_canonical_equivalence(function):
    assert function(unicodedata.normalize("NFD", "Cửa hàng"), "Cửa hàng") == 1


@pytest.mark.parametrize(
    "prediction,reference",
    [
        ("Cua hang", "Cửa hàng"),
        ("tổng", "Tổng"),
        ("125.001", "125.000"),
        ("1,5", "15"),
        ("-12", "12"),
        ("1.234", "1234"),
        (" 12", "12"),
    ],
)
def test_em_preserves_accents_case_digits_punctuation_and_whitespace(prediction, reference):
    assert exact_match(prediction, reference) == 0


@pytest.mark.parametrize(
    "prediction,reference,expected",
    [
        ("a a", "a a", 1),
        ("a a", "a", 2 / 3),
        ("a b b", "b b c", 2 / 3),
        ("125.000", "125.001", 0),
        ("Cà\nphê", "Cà phê", 1),
        ("", "", 1),
        ("", "answer", 0),
        ("answer", "", 0),
    ],
)
def test_token_f1_uses_multiset_overlap(prediction, reference, expected):
    assert token_f1(prediction, reference) == pytest.approx(expected)


@pytest.mark.parametrize(
    "prediction,reference,expected",
    [
        ("abc", "abc", 1),
        ("abc", "axc", 2 / 3),  # distance < 0.5
        ("ab", "ac", 0),  # exactly 0.5 must be zero
        ("abc", "axy", 0),  # distance > 0.5
        ("abc", "abcd", 0.75),
        ("abcd", "abc", 0.75),
        ("ab", "ba", 0),  # two edits, not Damerau transposition
        ("125.001", "125.000", 6 / 7),  # partial ANLS credit is NOT exact numeric correctness
        ("", "", 1),
        ("", "a", 0),
        ("a", "", 0),
    ],
)
def test_anls_distance_and_strict_threshold(prediction, reference, expected):
    assert anls(prediction, reference) == pytest.approx(expected)


def test_multi_reference_maximum_and_multipart_are_distinct():
    scores = score_answer("Cà phê", ("Coffee", "Cà phê"))
    assert scores.strict_nfc_em == scores.strict_nfc_token_f1 == scores.strict_nfc_anls == 1
    partial = score_answer("Trà", ("Trà ¡sep¿ Cà phê",))
    assert partial.strict_nfc_em == 0
    assert partial.strict_nfc_token_f1 == pytest.approx(0.4)
    assert exact_match("Trà\nCà phê", "Trà ¡sep¿ Cà phê") == 0
    assert exact_match("Trà ¡sep¿ Cà phê", "Cà phê ¡sep¿ Trà") == 0


@pytest.mark.parametrize("references", [[], (), [""], [" "], ["ok", ""], "answer"])
def test_invalid_reference_sets_are_not_silently_scored(references):
    with pytest.raises(ValueError):
        score_answer("answer", references)


def test_missing_answer_is_not_treated_as_empty_reference_match():
    for prediction in (None, ""):
        scores = score_answer(prediction, ("answer",))
        assert scores.strict_nfc_em == scores.strict_nfc_token_f1 == scores.strict_nfc_anls == 0
    with pytest.raises(ValidationError):
        GoldReference(qid="q", document_id="d", answers=("",))


def refs(count):
    return [
        GoldReference(qid=f"q{i}", document_id=f"d{i}", answers=("đúng",)) for i in range(count)
    ]


def test_qid_join_and_denominator_include_missing_abstention_and_error():
    predictions = [
        AnswerPrediction(qid="q3", status="error"),
        AnswerPrediction(qid="q0", status="answered", answer_raw="đúng"),
        AnswerPrediction(qid="q1", status="answered", answer_raw="sai"),
        AnswerPrediction(qid="q2", status="abstained"),
    ]
    result = evaluate_answers(refs(5), predictions)
    assert result.n_questions == 5
    assert (result.n_answered, result.n_abstained, result.n_error, result.n_missing) == (2, 1, 1, 1)
    assert result.strict_nfc_em == 0.2
    assert result.coverage == 0.4
    assert result.selective_em == 0.5
    assert result.protocol == "strict_nfc_v1"
    assert result.official_compatible is False


def test_zero_coverage_is_undefined_selective_accuracy():
    result = evaluate_answers(refs(2), [])
    assert result.coverage == result.strict_nfc_em == 0
    assert result.selective_em is None
    assert result.n_missing == 2


@pytest.mark.parametrize("defect", ["duplicate_gold", "duplicate_prediction", "unknown", "empty"])
def test_evaluation_rejects_misaligned_or_duplicated_sets(defect):
    gold = refs(1)
    predictions = [AnswerPrediction(qid="q0", status="answered", answer_raw="đúng")]
    if defect == "duplicate_gold":
        gold += gold
    elif defect == "duplicate_prediction":
        predictions += predictions
    elif defect == "unknown":
        predictions = [AnswerPrediction(qid="unknown", status="abstained")]
    else:
        gold = []
    with pytest.raises(ValueError):
        evaluate_answers(gold, predictions)


@pytest.mark.parametrize(
    "status,answer",
    [("answered", ""), ("answered", None), ("abstained", "đúng"), ("error", "đúng")],
)
def test_prediction_status_cannot_misrepresent_coverage(status, answer):
    with pytest.raises(ValidationError):
        AnswerPrediction(qid="q", status=status, answer_raw=answer)


def test_invalid_model_copy_is_revalidated_at_evaluator_boundary():
    prediction = AnswerPrediction(qid="q0", status="abstained")
    prediction = prediction.model_copy(update={"answer_raw": "đúng"})
    with pytest.raises(ValidationError):
        evaluate_answers(refs(1), [prediction])


@pytest.mark.parametrize("change", [{"n_missing": 0}, {"coverage": 0.5}, {"selective_em": 0}])
def test_report_contract_rejects_misleading_denominators(change):
    payload = evaluate_answers(refs(1), []).model_dump()
    payload.update(change)
    with pytest.raises(ValidationError):
        EvaluationSummary.model_validate(payload)
