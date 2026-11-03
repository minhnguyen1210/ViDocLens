"""Conservative lexical OCR support, never a semantic truth or answer correction."""

import re
import unicodedata
from dataclasses import dataclass

from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import FilterConfig, PartSupport


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def answer_type(value: str) -> str:
    if not any(c.isdigit() for c in value):
        return "text"
    without_units = re.sub(r"(?i)(vnd|vnđ|đồng|₫|đ|usd|eur)", "", value)
    return "hybrid" if any(c.isalpha() for c in without_units) else "numeric"


def question_type(question: str) -> str:
    """Question-only heuristic, not a gold taxonomy or semantic verifier."""
    q = normalize(question).casefold()
    for kind, cues in (
        ("total", ("tổng", "thanh toán")),
        ("date", ("ngày", "thời gian")),
        ("address", ("địa chỉ",)),
        ("merchant", ("cửa hàng", "đơn vị bán")),
        ("items", ("mặt hàng", "sản phẩm", "món")),
    ):
        if any(cue in q for cue in cues):
            return kind
    return "unknown"


def split_parts(raw: str, protocol: str) -> tuple[str, ...]:
    if protocol == "whole_answer_v1":
        return (raw,)
    if protocol != "literal_separator_v1":
        raise ValueError("unknown answer part protocol")
    # Newlines are layout, not inferred part delimiters. Preserve raw serialization.
    parts = tuple(raw.split("¡sep¿"))
    if any(not p.strip() for p in parts):
        raise ValueError("empty literal answer part")
    return parts


@dataclass(frozen=True)
class Candidate:
    text: str
    span_ids: tuple[str, ...]
    start: int
    end: int
    numeric_boundary: bool


def _numeric_neighbor(token: str) -> bool:
    return bool(
        any(c.isdigit() for c in token)
        or any(unicodedata.category(c) == "Sc" for c in token)
        or token.casefold()
        in {
            "-",
            "−",
            "–",
            "—",
            "﹣",
            "－",
            "+",
            "＋",
            "(",
            ")",
            ".",
            ",",
            ":",
            "/",
            "%",
            "₫",
            "đ",
            "vnd",
            "vnđ",
            "đồng",
            "$",
            "usd",
            "eur",
            "kg",
            "g",
            "l",
            "ml",
        }
    )


def candidates(ocr: OCRResult, config: FilterConfig) -> tuple[Candidate, ...]:
    rows = sorted(ocr.spans, key=lambda s: (s.reading_order, s.span_id))
    if len({s.span_id for s in rows}) != len(rows):
        raise ValueError("duplicate OCR span IDs")
    tokens = [
        (token, line, s.span_id)
        for line, s in enumerate(rows)
        for token in normalize(s.text_raw).split()
    ]
    if len(tokens) > config.max_document_tokens:
        raise ValueError("ocr_token_limit")
    output = []
    for start in range(len(tokens)):
        for end in range(start + 1, min(len(tokens), start + config.max_span_tokens) + 1):
            window = tokens[start:end]
            if window[-1][1] - window[0][1] >= config.max_consecutive_lines:
                break
            text = " ".join(t[0] for t in window)
            if len(text) > config.max_answer_characters:
                break
            # Whole whitespace tokens; also reject stripping a separated sign/unit/number.
            left_ok = start == 0 or not _numeric_neighbor(tokens[start - 1][0])
            right_ok = end == len(tokens) or not _numeric_neighbor(tokens[end][0])
            output.append(
                Candidate(
                    text,
                    tuple(dict.fromkeys(t[2] for t in window)),
                    start,
                    end,
                    left_ok and right_ok,
                )
            )
    return tuple(output)


def distance(a: str, b: str) -> float:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1] / max(len(a), len(b))


def match_part(raw: str, choices: tuple[Candidate, ...], config: FilterConfig) -> PartSupport:
    target = normalize(raw)
    base = dict(text_raw=raw, text_normalized=target)
    if len(target) > config.max_answer_characters:
        return PartSupport(**base, support="none", reason="answer_length_limit")
    numeric = any(c.isdigit() for c in target)
    scored = []
    threshold = config.text_max_normalized_edit_distance
    for c in choices:
        if numeric and not c.numeric_boundary:
            continue
        if c.text == target:
            scored.append((0.0, c))
        elif (
            not numeric
            and not any(ch.isdigit() for ch in c.text)
            and len(target) >= config.min_fuzzy_characters
            and abs(len(target) - len(c.text)) / max(len(target), len(c.text))
            <= threshold + config.min_candidate_margin
        ):
            d = distance(target, c.text)
            if d <= threshold + config.min_candidate_margin:
                scored.append((d, c))
    scored.sort(key=lambda pair: (pair[0], pair[1].start, pair[1].end))
    if not scored or scored[0][0] > threshold:
        return PartSupport(**base, support="none", reason="no_ocr_support")
    best, occurrence = scored[0]
    # Repeated text at distinct locations is ambiguous, including equal exact matches.
    if len(scored) > 1 and scored[1][0] - best < config.min_candidate_margin - 1e-12:
        return PartSupport(
            **base, support="none", reason="ambiguous_ocr_support", candidate_count=len(scored)
        )
    return PartSupport(
        **base,
        support="exact" if best == 0 else "fuzzy",
        reason="lexical_support_only",
        span_ids=occurrence.span_ids,
        token_start=occurrence.start,
        token_end=occurrence.end,
        distance=best,
        candidate_count=len(scored),
    )
