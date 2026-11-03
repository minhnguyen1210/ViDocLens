"""Conservative, versioned label/geometry heuristic; not a learned semantic oracle."""

import re

from vidoclens.filtering.matching import normalize

CUES = {
    "total": (
        "tổng thanh toán",
        "tổng cộng",
        "tổng tiền",
        "thành tiền",
        "grand total",
        "total amount",
        "total",
    ),
    "subtotal": ("tạm tính", "cộng tiền hàng", "subtotal", "sub total"),
    "tendered": ("khách đưa", "tiền nhận", "cash received", "cash tendered"),
    "change": ("tiền thừa", "tiền trả lại", "change"),
    "date": ("ngày", "thời gian", "date", "timestamp"),
    "address": ("địa chỉ", "address"),
    "merchant": ("tên cửa hàng", "đơn vị bán", "tên quán", "seller", "merchant"),
}


def cue_fields(text):
    text = normalize(text).casefold()
    return {
        field
        for field, cues in CUES.items()
        if any(re.search(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", text) for cue in cues)
    }


def question_field(question):
    found = cue_fields(question)
    if not found and "thanh toán" in normalize(question).casefold():
        found = {"total"}
    return next(iter(found)) if len(found) == 1 else "unknown"


def field_support(expected, candidate, spans, max_gap):
    if expected == "unknown":
        return "unknown", ()
    anchor = spans[candidate.span_ids[0]].box
    labels = []
    for span in spans.values():
        fields = cue_fields(span.text_raw)
        if not fields:
            continue
        box = span.box
        if span.span_id in candidate.span_ids:
            rank = 0.0
        else:
            overlap_y = min(box.y1, anchor.y1) - max(box.y0, anchor.y0)
            same_line = overlap_y >= 0.5 * min(box.y1 - box.y0, anchor.y1 - anchor.y0)
            if same_line and box.x1 <= anchor.x0 + 0.01:
                rank = 0.001 + max(0, anchor.x0 - box.x1)
            elif 0 <= anchor.y0 - box.y1 <= max_gap and min(box.x1, anchor.x1) > max(
                box.x0, anchor.x0
            ):
                rank = 1.0 + anchor.y0 - box.y1
            else:
                continue
        labels.append((rank, span.span_id, fields))
    if not labels:
        return "unknown", ()
    best = min(r[0] for r in labels)
    nearest = [r for r in labels if abs(r[0] - best) < 1e-9]
    fields = set().union(*(r[2] for r in nearest))
    status = "pass" if fields == {expected} else "fail" if expected not in fields else "unknown"
    return status, tuple(sorted(r[1] for r in nearest))
