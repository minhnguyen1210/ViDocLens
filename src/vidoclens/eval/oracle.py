"""Bounded lexical OCR oracle; uses gold, cannot be an inference/filter component."""

import re
import unicodedata
from collections.abc import Sequence

from vidoclens.contracts.models import OCRResult
from vidoclens.eval.metrics import _edit_distance, exact_match, score_answer, token_f1

SPAN_PROTOCOL = {
    "name": "ocr_contiguous_4lines_24tokens_v1",
    "max_consecutive_lines": 4,
    "max_tokens_per_span": 24,
    "max_tokens_per_document": 4096,
    "joins": [" ", "\n", " ¡sep¿ "],
    "selection": "max strict EM, then max multiset F1, then shortest and lexical",
    "uses_gold": True,
    "numeric_fuzzy_correction": False,
}


def answer_parts(raw: str) -> tuple[str, ...]:
    """Diagnostic only; raw/full-answer scoring is never replaced by part scoring."""
    return tuple(re.split(r"\r\n|\n|¡sep¿", raw))


def spans(result: OCRResult) -> tuple[str, ...]:
    result = OCRResult.model_validate(result.model_dump())
    if result.status not in {"ok", "empty"}:
        return ()
    lines = [s.text_raw for s in sorted(result.spans, key=lambda s: (s.reading_order, s.span_id))]
    if sum(len(line.split()) for line in lines) > 4096:
        raise ValueError("OCR exceeds registered oracle token cap")
    candidates = set()
    for i, line in enumerate(lines):
        if line.strip() and len(line.split()) <= 24:
            candidates.add(line)
        for j in range(i + 1, min(len(lines), i + 4) + 1):
            block = lines[i:j]
            for join in (" ", "\n", " ¡sep¿ "):
                full = join.join(block)
                if full.strip() and len(full.split()) <= 24:
                    candidates.add(full)
            # Token windows can cross a line boundary but never more than four lines.
            tokens = " ".join(block).split()
            for start in range(len(tokens)):
                for end in range(start + 1, min(len(tokens), start + 24) + 1):
                    candidates.add(" ".join(tokens[start:end]))
    return tuple(sorted(candidates, key=lambda s: (len(s), s)))


def matched_ocr(candidates: Sequence[str], references: Sequence[str]) -> dict:
    if not references or any(not r.strip() for r in references):
        raise ValueError("nonblank full references required")
    # Exact string preservation, including CRLF/multipart punctuation, wins first.
    exact = [s for s in candidates if any(exact_match(s, r) for r in references)]
    if exact:
        prediction = min(exact, key=lambda s: (len(s), s))
    elif candidates:
        prediction = min(
            candidates, key=lambda s: (-max(token_f1(s, r) for r in references), len(s), s)
        )
    else:
        prediction = None
    return {
        "prediction": prediction,
        "scores": score_answer(prediction, references).model_dump(),
        "exact_span_recall": float(bool(exact)),
        "candidate_count": len(candidates),
    }


def character_error_rate(pairs: Sequence[tuple[str, str]]) -> dict:
    if not pairs or any(not reference for _, reference in pairs):
        raise ValueError("CER needs nonempty reference transcriptions")
    errors = characters = 0
    for prediction, reference in pairs:
        prediction, reference = (unicodedata.normalize("NFC", s) for s in (prediction, reference))
        errors += _edit_distance(prediction, reference)
        characters += len(reference)
    return {
        "cer": errors / characters,
        "edit_errors": errors,
        "reference_characters": characters,
        "normalization": "NFC only; preserve case, spaces, punctuation and digits",
    }
