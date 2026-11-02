"""Seeded QA-weighted bootstrap resampling whole receipt/leakage components."""

import math
import random
from collections import defaultdict
from collections.abc import Mapping

from vidoclens.common.pilot import percentile


def group_bootstrap(
    scores: Mapping[str, float],
    groups: Mapping[str, str],
    *,
    paired_scores: Mapping[str, float] | None = None,
    resamples: int = 2000,
    seed: int = 42,
) -> dict:
    if set(scores) != set(groups) or not scores:
        raise ValueError("scores/groups must have identical nonempty qid populations")
    if paired_scores is not None and set(paired_scores) != set(scores):
        raise ValueError("paired comparison requires identical qid population")
    if resamples < 2:
        raise ValueError("at least two resamples required")
    clustered = defaultdict(list)
    for qid in sorted(scores):
        value = scores[qid]
        other = paired_scores[qid] if paired_scores is not None else 0.0
        if not groups[qid] or not all(math.isfinite(v) and 0 <= v <= 1 for v in (value, other)):
            raise ValueError("invalid group or score outside [0,1]")
        clustered[groups[qid]].append(value - other)
    if len(clustered) < 2:
        raise ValueError("bootstrap requires at least two independent groups")
    totals = [(sum(clustered[g]), len(clustered[g])) for g in sorted(clustered)]
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        sample = [totals[rng.randrange(len(totals))] for _ in totals]
        estimates.append(sum(v for v, _ in sample) / sum(n for _, n in sample))
    return {
        "point_estimate": sum(v for v, _ in totals) / sum(n for _, n in totals),
        "lower_95": percentile(estimates, 0.025),
        "upper_95": percentile(estimates, 0.975),
        "n_qa": len(scores),
        "n_groups": len(totals),
        "resamples": resamples,
        "seed": seed,
        "unit": "receipt_or_conservative_leakage_component",
        "estimand": "QA_weighted_mean",
        "paired_difference": paired_scores is not None,
        "training_variance_included": False,
    }
