"""Project strict_nfc_v1 metrics. Not a claim of parity with the official scorer."""

import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence

from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction, AnswerScores, EvaluationSummary


def _nfc(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("metrics require text strings")
    return unicodedata.normalize("NFC", text)


def exact_match(prediction: str, reference: str) -> float:
    return float(_nfc(prediction) == _nfc(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Multiset whitespace tokens; do not strip punctuation, digits, case or accents."""
    predicted, expected = _nfc(prediction).split(), _nfc(reference).split()
    if not predicted or not expected:
        return float(predicted == expected)
    overlap = sum((Counter(predicted) & Counter(expected)).values())
    return 2 * overlap / (len(predicted) + len(expected))


def _edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def anls(prediction: str, reference: str) -> float:
    predicted, expected = _nfc(prediction), _nfc(reference)
    length = max(len(predicted), len(expected))
    if not length:
        return 1.0
    distance = _edit_distance(predicted, expected)
    # Integer comparison enforces strict d < 0.5 without floating point boundary drift.
    return 1 - distance / length if 2 * distance < length else 0.0


def score_answer(prediction: str | None, references: Sequence[str]) -> AnswerScores:
    """Maximum per metric over FULL alternative answers, never over individual parts."""
    if isinstance(references, (str, bytes)) or not references:
        raise ValueError("references must be a nonempty sequence of full answers")
    if any(not isinstance(value, str) or not value.strip() for value in references):
        raise ValueError("answerable references must be nonblank strings")
    if prediction is None:
        return AnswerScores(strict_nfc_em=0, strict_nfc_token_f1=0, strict_nfc_anls=0)
    return AnswerScores(
        strict_nfc_em=max(exact_match(prediction, ref) for ref in references),
        strict_nfc_token_f1=max(token_f1(prediction, ref) for ref in references),
        strict_nfc_anls=max(anls(prediction, ref) for ref in references),
    )


def evaluate_answers(
    references: Iterable[GoldReference], predictions: Iterable[AnswerPrediction]
) -> EvaluationSummary:
    """Join by qid; reject unknown/duplicate IDs, count absent predictions as missing failures."""
    gold, outputs = {}, {}
    for record in references:
        record = GoldReference.model_validate(record.model_dump())
        if record.qid in gold:
            raise ValueError("duplicate reference qid")
        gold[record.qid] = record
    if not gold:
        raise ValueError("cannot evaluate an empty reference set")
    for record in predictions:
        record = AnswerPrediction.model_validate(record.model_dump())
        if record.qid not in gold or record.qid in outputs:
            raise ValueError("unknown or duplicate prediction qid")
        outputs[record.qid] = record
    counts = Counter(record.status for record in outputs.values())
    em = f1 = similarity = 0.0
    for qid, reference in gold.items():
        predicted = outputs.get(qid)
        scores = score_answer(predicted.answer_raw if predicted else None, reference.answers)
        em += scores.strict_nfc_em
        f1 += scores.strict_nfc_token_f1
        similarity += scores.strict_nfc_anls
    total, answered = len(gold), counts["answered"]
    return EvaluationSummary(
        strict_nfc_em=em / total,
        strict_nfc_token_f1=f1 / total,
        strict_nfc_anls=similarity / total,
        n_questions=total,
        n_answered=answered,
        n_abstained=counts["abstained"],
        n_error=counts["error"],
        n_missing=total - len(outputs),
        coverage=answered / total,
        selective_em=em / answered if answered else None,
    )
