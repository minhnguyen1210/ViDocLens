"""Blind OOD review packets and evidence checks; no images downloaded or labels inferred."""

import math

from vidoclens.common.pilot import sha256
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.filtering.io import digest, revalidate


def review_packets(plan, inventory):
    plan = revalidate(plan)
    if not plan.local_research_rights_attested:
        raise PermissionError("OOD local research rights not attested")
    if sha256(inventory) != plan.protected_inventory_sha256:
        raise ValueError("protected inventory changed")
    images = [
        CorpusImage.model_validate_json(line)
        for line in inventory.read_text(encoding="utf-8").splitlines()
    ]
    if not images:
        raise ValueError("protected corpus inventory must not be empty")
    raw = {r.raw_image_sha256 for r in images}
    pixels = {r.canonical_pixel_sha256 for r in images}
    if any(t.image_sha256 in raw or t.canonical_pixel_sha256 in pixels for t in plan.tasks):
        raise ValueError("OOD overlaps protected corpus")
    known = {}
    for task in plan.tasks:
        for key in (task.image_sha256, task.canonical_pixel_sha256):
            if key in known and known[key] != task.document_id:
                raise ValueError("duplicate OOD images under different document IDs")
            known[key] = task.document_id
    ranked = sorted(plan.tasks, key=lambda t: (digest([plan.seed, t.qid]), t.qid))
    reviewed = ranked[: math.ceil(len(ranked) * plan.second_review_fraction)]
    primary = {
        "protocol": "blind_ood_packet_v1",
        "plan_sha256": digest(plan),
        "stage": "primary",
        "fixture_only": plan.fixture_only,
        "tasks": [t.model_dump(mode="json") for t in ranked],
    }
    second = primary | {"stage": "second", "tasks": [t.model_dump(mode="json") for t in reviewed]}
    return primary, second


def submission_template(packet):
    return {
        "packet_sha256": digest(packet),
        "fixture_only": packet["fixture_only"],
        "reviewer": "",
        "reviewer_type": "human",
        "reviewed_at": None,
        "blind_image_review_attested": False,
        "labels": [
            {"qid": t["qid"], "answerable": None, "full_answers": [], "evidence_boxes": []}
            for t in packet["tasks"]
        ],
    }


def reconcile(plan, inventory, primary, second, resolutions=()):
    plan, primary, second = (revalidate(v) for v in (plan, primary, second))
    packets = review_packets(plan, inventory)
    for packet, submission in zip(packets, (primary, second), strict=True):
        if (
            submission.packet_sha256 != digest(packet)
            or submission.fixture_only != plan.fixture_only
            or {r.qid for r in submission.labels} != {t["qid"] for t in packet["tasks"]}
        ):
            raise ValueError("review submission does not cover exact blind packet")
    if second.reviewed_at < primary.reviewed_at:
        raise ValueError("second review timestamp predates primary")
    same_person = primary.reviewer.strip().casefold() == second.reviewer.strip().casefold()
    if same_person and (second.reviewed_at - primary.reviewed_at).total_seconds() < 86400:
        raise ValueError("same-person blind recheck requires at least 24 hours in this protocol")
    first = {r.qid: r for r in primary.labels}
    other = {r.qid: r for r in second.labels}
    resolutions = [revalidate(r) for r in resolutions]
    adjudicated = {r.qid: r for r in resolutions}
    disagreements = {qid for qid, r in other.items() if digest(r) != digest(first[qid])}
    if len(adjudicated) != len(resolutions) or adjudicated.keys() != disagreements:
        raise ValueError(
            "every disagreement needs exactly one human adjudication; no extra records"
        )
    for qid, resolution in adjudicated.items():
        if resolution.primary_label_sha256 != digest(
            first[qid]
        ) or resolution.second_label_sha256 != digest(other[qid]):
            raise ValueError("adjudication is not bound to both human records")
        first[qid] = resolution.final_label
    return {
        "protocol": "human_ood_curation_v1",
        "plan_sha256": digest(plan),
        "fixture_only": plan.fixture_only,
        "primary_sha256": digest(primary),
        "second_sha256": digest(second),
        "resolutions_sha256": digest([r.model_dump(mode="json") for r in resolutions]),
        "labels": [first[q].model_dump(mode="json") for q in sorted(first)],
        "qa_count": len(first),
        "document_count": len({t.document_id for t in plan.tasks}),
        "second_reviewed_qa": len(other),
        "second_review_fraction": len(other) / len(first),
        "review_mode": "delayed_blind_same_human" if same_person else "independent_human",
        "disagreements": len(disagreements),
        "human_review_requirement_met": True,
        "final_test_execution_enabled": False,
        "g5_certified": False,
        "limitations": [
            "rights, near-duplicate resolution and unseen-source status are owner attestations",
            "automatic overlap check covers byte/pixel hashes in supplied inventory only",
            "same-person review is not inter-annotator agreement",
            "sample size/diversity targets and final eligibility still need owner review",
        ],
    }
