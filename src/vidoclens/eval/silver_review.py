"""Seeded stratified human audit, blind to gold and filter outcome during annotation."""

from collections import Counter

from vidoclens.contracts.silver_review import SilverReviewItem, SilverReviewPacket
from vidoclens.eval.silver import audit_filter
from vidoclens.filtering.io import digest, revalidate

STRATA = ("kept_correct", "kept_wrong", "rejected_correct", "rejected_wrong")


def make_review_packet(pool, batch, run, references, ocr, *, per_stratum=25, seed=42):
    if not isinstance(per_stratum, int) or per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    references, ocr = list(references), [revalidate(r) for r in ocr]
    report = audit_filter(pool, batch, run, references)
    # Same ordering/hash definition as filter_batch; reject wrong OCR payload.
    from vidoclens.filtering.pipeline import filter_batch

    if digest(filter_batch(pool, batch, ocr, run.config)) != digest(run):
        raise ValueError("review OCR differs from filter evidence")
    samples = {s.question.qid: s for s in pool.samples}
    decisions = {d.qid: d for d in run.decisions}
    by_document = {r.document_id: r for r in ocr}
    selected, strata = {}, {}
    for name in STRATA:
        population = report["review_qids"].get(name, [])
        chosen = sorted(population, key=lambda q: (digest([seed, name, q]), q))[:per_stratum]
        strata[name] = {
            "population": len(population),
            "sampled": len(chosen),
            "inclusion_probability": len(chosen) / len(population) if population else None,
        }
        selected.update({q: name for q in chosen})
    # Shuffle all strata together and omit gold/outcome from the reviewer-facing file.
    qids = sorted(selected, key=lambda q: (digest(["blind_order", seed, q]), q))
    if not qids:
        raise ValueError("no eligible labels to review")
    packet = SilverReviewPacket(
        pool_sha256=digest(pool),
        filter_run_sha256=digest(run),
        audit_sha256=digest(report),
        fixture_only=batch.fixture_only,
        seed=seed,
        per_stratum=per_stratum,
        items=tuple(
            SilverReviewItem(
                sample=samples[q],
                answer_raw=decisions[q].answer_raw,
                ocr=by_document.get(samples[q].question.document_id),
            )
            for q in qids
        ),
    )
    key = {
        "protocol": "silver_review_sampling_key_v1",
        "packet_sha256": digest(packet),
        "strata": strata,
        "outcomes": selected,
        "sampling_unit": "QA within outcome stratum",
        "population_accuracy_claim": False,
    }
    template = {
        "protocol": "silver_human_review_v1",
        "packet_sha256": digest(packet),
        "fixture_only": packet.fixture_only,
        "annotator_kind": "human",
        "reviewer": "",
        "image_inspection_attested": False,
        "judgments": [
            {
                "qid": q,
                "correctness": None,
                "semantic_field": None,
                "ocr_quality": None,
                "error_tags": [],
                "note": "",
            }
            for q in qids
        ],
    }
    return packet, key, template


def summarize_review(packet, key, review):
    packet, review = revalidate(packet), revalidate(review)
    qids = {r.sample.question.qid for r in packet.items}
    if (
        key.get("protocol") != "silver_review_sampling_key_v1"
        or key.get("packet_sha256") != digest(packet)
        or review.packet_sha256 != digest(packet)
        or review.fixture_only != packet.fixture_only
        or set(key.get("outcomes", {})) != qids
        or {r.qid for r in review.judgments} != qids
        or set(key.get("strata", {})) != set(STRATA)
        or any(v not in STRATA for v in key["outcomes"].values())
    ):
        raise ValueError("human review must cover the exact packet and fixture provenance")
    judgments = {r.qid: r for r in review.judgments}
    summaries = {}
    for name in STRATA:
        rows = [judgments[q] for q, group in key["outcomes"].items() if group == name]
        declared = key["strata"][name]
        if declared["sampled"] != len(rows) or declared["population"] < len(rows):
            raise ValueError("sampling key counts mismatch")
        expected = "correct" if name.endswith("_correct") else "wrong"
        summaries[name] = declared | {
            "human_correctness_counts": dict(Counter(r.correctness for r in rows)),
            "disagreements_with_automatic_gold_em": sum(
                r.correctness not in {expected, "uncertain"} for r in rows
            ),
            "semantic_field_counts": dict(Counter(r.semantic_field for r in rows)),
            "ocr_quality_counts": dict(Counter(r.ocr_quality for r in rows)),
            "error_tags": dict(Counter(tag for r in rows for tag in set(r.error_tags))),
        }
    return {
        "protocol": "silver_human_review_summary_v1",
        "packet_sha256": digest(packet),
        "review_sha256": digest(review),
        "fixture_only": packet.fixture_only,
        "reviewer": review.reviewer,
        "reviewed": len(qids),
        "by_stratum": summaries,
        "human_attestation_received": True,
        "gold_modified": False,
        "limitations": [
            "reviewer identity and image inspection are attestations, not authentication",
            "stratified sample counts are not whole-pool accuracy; no independent-QA CI",
            "human review may reveal gold disagreement; never automatically replace gold",
            "holdout findings cannot tune this frozen filter",
        ],
    }
