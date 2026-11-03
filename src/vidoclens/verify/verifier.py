"""CPU P3-check/P3-snap. Never reads gold, invokes a model or changes F1."""

import re
import unicodedata
from pathlib import Path

from vidoclens.contracts import verification as contracts
from vidoclens.contracts.silver import FilterConfig
from vidoclens.contracts.verification import VerificationDecision, VerifierCandidate, VerifierPart
from vidoclens.filtering import matching
from vidoclens.filtering.io import digest, revalidate
from vidoclens.verify import fields


def implementation_hash():
    return digest(
        [
            Path(p).read_text(encoding="utf-8")
            for p in (__file__, fields.__file__, contracts.__file__, matching.__file__)
        ]
    )


def protected(text):
    return any(
        c.isdigit() or unicodedata.category(c) == "Sc" or c in "+-−–—﹣－＋%" for c in text
    ) or bool(
        re.search(r"(?i)(?<!\w)(vnd|vnđ|đồng|đ|usd|eur|kg|ml|kilogram|gram|litre|lít)(?!\w)", text)
    )


def _choices(raw, choices, spans, config, expected):
    target = matching.normalize(raw)
    result = []
    for c in choices:
        boxes = [spans[s].box for s in c.span_ids]
        if any(b.y0 - a.y1 > config.max_span_line_gap for a, b in zip(boxes, boxes[1:])):
            continue
        numeric = any(ch.isdigit() for ch in raw)
        if numeric and not c.numeric_boundary:
            continue
        if c.text == target:
            distance = 0.0
        elif protected(raw) or protected(c.text) or len(target) < config.min_text_length:
            continue
        elif (
            abs(len(target) - len(c.text)) / max(len(target), len(c.text))
            > config.text_threshold + config.candidate_margin
        ):
            continue
        else:
            distance = matching.distance(target, c.text)
            if distance > config.text_threshold + config.candidate_margin:
                continue
        status, labels = fields.field_support(expected, c, spans, config.max_label_gap)
        result.append(
            VerifierCandidate(
                text=c.text,
                span_ids=c.span_ids,
                boxes=tuple(boxes),
                token_start=c.start,
                token_end=c.end,
                distance=distance,
                field_status=status,
                field_label_ids=labels,
            )
        )
    return sorted(result, key=lambda r: (r.distance, r.token_start, r.token_end))


def verify(value, config, *, snap=False):
    value, config = revalidate(value), revalidate(config)
    prediction, ocr = value.prediction, value.ocr
    raw = prediction.answer_raw
    field = fields.question_field(value.sample.question.question_raw)
    base = dict(
        qid=prediction.qid,
        input_sha256=digest(value),
        config_sha256=digest(config),
        implementation_sha256=implementation_hash(),
        variant="P3-snap" if snap else "P3-check",
        answer_before=raw,
        question_field=field,
    )

    def reject(reason, parts=()):
        return VerificationDecision(**base, status="abstained", reason=reason, parts=tuple(parts))

    if prediction.status != "answered":
        return reject("prediction_" + prediction.status)
    if ocr is None or ocr.status != "ok" or not ocr.spans:
        return reject("ocr_unavailable")
    if len(raw) > config.max_answer_characters:
        return reject("answer_length_limit")
    spans = {s.span_id: s for s in ocr.spans}
    if len(spans) != len(ocr.spans) or len({s.reading_order for s in ocr.spans}) != len(ocr.spans):
        raise ValueError("duplicate OCR span ID/reading order")
    # Validate nested mutable OCR fields as well as outer frozen records.
    if any(s.text_nfc != unicodedata.normalize("NFC", s.text_raw) for s in ocr.spans):
        raise ValueError("OCR NFC text mismatch")
    try:
        parts = matching.split_parts(raw, config.part_protocol)
        choices = matching.candidates(
            ocr,
            FilterConfig(
                max_document_tokens=config.max_document_tokens,
                max_span_tokens=config.max_span_tokens,
                max_consecutive_lines=config.max_lines,
                max_answer_characters=config.max_answer_characters,
            ),
        )
    except ValueError as error:
        if str(error) in {"ocr_token_limit", "empty literal answer part"}:
            return reject(str(error))
        raise
    traces, used, scores = [], set(), []
    for part in parts:
        candidates = _choices(part, choices, spans, config, field)
        supported = [c for c in candidates if c.field_status == "pass"]
        alternatives = tuple(candidates[:3])
        if not supported or supported[0].distance > config.text_threshold:
            reason = (
                "wrong_field_risk"
                if any(c.field_status == "fail" for c in candidates)
                else "field_unknown"
                if candidates
                else "missing_evidence"
            )
            traces.append(VerifierPart(before=part, alternatives=alternatives, reason=reason))
            return reject(reason, traces)
        best = supported[0]
        if (
            len(supported) > 1
            and supported[1].distance - best.distance < config.candidate_margin - 1e-12
        ):
            traces.append(
                VerifierPart(
                    before=part, alternatives=tuple(supported[:3]), reason="ambiguous_span"
                )
            )
            return reject("ambiguous_span", traces)
        tokens = set(range(best.token_start, best.token_end))
        if used & tokens:
            return reject("overlapping_part_evidence", traces)
        used |= tokens
        # Conservative v1: hybrid/multipart containing any protected content is never edited.
        after = best.text if snap and best.distance > 0 and not protected(raw) else part
        traces.append(
            VerifierPart(
                before=part,
                after=after,
                selected=best,
                alternatives=alternatives,
                reason="field_and_lexical_support",
            )
        )
        scores.append(1.0 - best.distance)
    final = (
        "¡sep¿".join(t.after for t in traces)
        if config.part_protocol == "literal_separator_v1"
        else traces[0].after
    )
    changed = final != raw
    if changed:
        updated = value.model_copy(
            update={"prediction": prediction.model_copy(update={"answer_raw": final})}
        )
        if (
            protected(raw)
            or protected(final)
            or verify(updated, config, snap=False).status != "answered"
        ):
            return reject("snap_recheck_failed", traces)
    return VerificationDecision(
        **base,
        status="answered",
        answer_after=final,
        reason="snapped_and_rechecked" if changed else "supported",
        parts=tuple(traces),
        snap_applied=changed,
        rule_score=min(scores),
    )
