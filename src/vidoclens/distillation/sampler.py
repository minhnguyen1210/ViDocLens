"""Equal source exposure and replayable sample order independent of global RNG."""

import hashlib
import random
from collections import Counter

from vidoclens.filtering.io import digest


def cyclic_order(count, length, seed, source):
    if count < 1 or length < 1 or source not in {"gold", "silver"}:
        raise ValueError("sampler needs nonempty registered sources")
    output, epoch = [], 0
    while len(output) < length:
        state = int.from_bytes(hashlib.sha256(f"{seed}:{source}:{epoch}".encode()).digest(), "big")
        order = list(range(count))
        random.Random(state).shuffle(order)
        output.extend(order)
        epoch += 1
    return output[:length]


def schedule(rows, seed, updates=191, accumulation=16):
    if accumulation < 2 or accumulation % 2 or updates < 1:
        raise ValueError("1:1 sampler requires even positive accumulation")
    groups = {
        source: sorted(
            (i for i, r in enumerate(rows) if r.source == source),
            key=lambda i: rows[i].input.question.qid,
        )
        for source in ("gold", "silver")
    }
    per_source = updates * accumulation // 2
    orders = {
        s: [indices[i] for i in cyclic_order(len(indices), per_source, seed, s)]
        for s, indices in groups.items()
    }
    return [index for pair in zip(orders["gold"], orders["silver"], strict=True) for index in pair]


def schedule_digest(rows, indices):
    return digest([[rows[i].source, rows[i].input.question.qid] for i in indices])


def exposure_counts(rows, indices):
    counts = Counter(rows[i].input.question.qid for i in indices)
    return {
        source: {
            r.input.question.qid: counts[r.input.question.qid] for r in rows if r.source == source
        }
        for source in ("gold", "silver")
    }
