"""LiGT scorer compatibility at commit 5b4376b with explicit anls 0.0.2 semantics.

Upstream leaves its anls dependency unpinned; this is not historical run reproduction.
"""

from collections.abc import Sequence

from vidoclens.eval.metrics import _edit_distance

PROTOCOL = "ligt_5b4376b_anls_0_0_2_v1"


def compatible_scores(prediction: str | None, references: Sequence[str]) -> dict[str, float]:
    if (
        isinstance(references, (str, bytes))
        or not references
        or any(not r.strip() for r in references)
    ):
        raise ValueError("nonblank full references required")
    if prediction is None:
        return dict(accuracy=0.0, set_token_f1=0.0, anls=0.0)
    # base_executor._evaluate_metrics strips outer whitespace, preserves internal separators.
    prediction = prediction.strip()
    references = [r.strip() for r in references]
    accuracy = sum(prediction == r for r in references) / len(references)
    a = prediction.split()
    f1 = 0.0
    similarities = []
    for reference in references:
        b = reference.split()
        f1 += (2 * len(set(a) & set(b)) / (len(a) + len(b))) if a and b else float(a == b)
        x, y = " ".join(prediction.lower().split()), " ".join(reference.lower().split())
        # This unusual upper-length denominator is present in the pinned ANLS wheel.
        length = max(len(x.upper()), len(y.upper()))
        distance = _edit_distance(x, y)
        similarities.append(
            1.0 if not length else (1 - distance / length if 2 * distance < length else 0.0)
        )
    return dict(accuracy=accuracy, set_token_f1=f1 / len(references), anls=max(similarities))
