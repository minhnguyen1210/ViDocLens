"""Review workflow tests use invented text and hashes, not human gold."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_image_ingestion import record
from test_silver import HASH

from vidoclens.common.pilot import sha256
from vidoclens.contracts.models import Box
from vidoclens.contracts.ood_review import (
    OODHumanLabel,
    OODHumanSubmission,
    OODResolution,
    OODReviewPlan,
    OODReviewTask,
)
from vidoclens.filtering.io import digest
from vidoclens.verify.ood import reconcile, review_packets, submission_template


def plan(inventory, n=6):
    return OODReviewPlan(
        fixture_only=True,
        protected_inventory_sha256=sha256(inventory),
        dedup_evidence_sha256=HASH,
        local_research_rights_attested=True,
        tasks=tuple(
            OODReviewTask(
                qid=f"synthetic-ood:{i}:question:1",
                document_id=f"synthetic-ood:{i}",
                image_sha256=digest(["ood-bytes", i]),
                canonical_pixel_sha256=digest(["ood-pixels", i]),
                source_domain="synthetic-fixture",
                shift_axes=("layout",),
                rights_evidence_sha256=HASH,
                question="Tổng tiền?",
                question_type="total",
            )
            for i in range(n)
        ),
    )


def submissions(p, inventory, *, same_person=False):
    packets = review_packets(p, inventory)
    return tuple(
        OODHumanSubmission(
            packet_sha256=digest(packet),
            fixture_only=True,
            reviewer="synthetic-reviewer-a" if same_person or i == 0 else "synthetic-reviewer-b",
            reviewed_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            blind_image_review_attested=True,
            labels=tuple(
                OODHumanLabel(
                    qid=t["qid"],
                    answerable=True,
                    full_answers=("125",),
                    evidence_boxes=(Box(x0=0.1, y0=0.1, x1=0.9, y1=0.2),),
                )
                for t in packet["tasks"]
            ),
        )
        for i, packet in enumerate(packets)
    )


@pytest.fixture
def inventory(tmp_path):
    path = tmp_path / "inventory.jsonl"
    path.write_text(record(1).model_dump_json() + "\n", encoding="utf-8")
    return path


def test_blind_seeded_packets_and_ceil_twenty_percent(inventory):
    p = plan(inventory)
    primary, second = review_packets(p, inventory)
    assert len(primary["tasks"]) == 6 and len(second["tasks"]) == 2
    assert review_packets(p, inventory) == (primary, second)
    assert not any("answer" in k or "prediction" in k for task in primary["tasks"] for k in task)
    with pytest.raises(ValidationError):
        OODHumanSubmission.model_validate(submission_template(primary))
    a, b = submissions(p, inventory)
    report = reconcile(p, inventory, a, b)
    assert report["fixture_only"] and report["second_review_fraction"] == 1 / 3
    assert report["human_review_requirement_met"] and not report["g5_certified"]
    assert not report["final_test_execution_enabled"]


@pytest.mark.parametrize("kind", ["raw", "pixels", "rights", "unseen", "near_duplicates"])
def test_ineligible_ood_refused(inventory, kind):
    p = plan(inventory)
    if kind in {"raw", "pixels"}:
        key = "image_sha256" if kind == "raw" else "canonical_pixel_sha256"
        p = p.model_copy(
            update={"tasks": (p.tasks[0].model_copy(update={key: record(1).raw_image_sha256}),)}
        )
        with pytest.raises(ValueError, match="overlaps"):
            review_packets(p, inventory)
    elif kind == "rights":
        with pytest.raises(PermissionError, match="rights"):
            review_packets(
                p.model_copy(update={"local_research_rights_attested": False}), inventory
            )
    elif kind == "unseen":
        with pytest.raises(ValidationError):
            OODReviewTask.model_validate(
                p.tasks[0].model_dump() | {"previously_model_reviewed": True}
            )
    else:
        with pytest.raises(ValidationError):
            OODReviewPlan.model_validate(p.model_dump() | {"unresolved_near_duplicates": 1})


def test_same_human_delay_and_exact_coverage(inventory):
    p = plan(inventory)
    a, b = submissions(p, inventory, same_person=True)
    assert reconcile(p, inventory, a, b)["review_mode"] == "delayed_blind_same_human"
    with pytest.raises(ValueError, match="24 hours"):
        reconcile(
            p,
            inventory,
            a,
            b.model_copy(update={"reviewed_at": a.reviewed_at + timedelta(hours=23)}),
        )
    with pytest.raises(ValueError, match="exact blind packet"):
        reconcile(p, inventory, a, b.model_copy(update={"labels": b.labels[:1]}))
    with pytest.raises(ValidationError):
        OODHumanSubmission.model_validate(b.model_dump() | {"reviewer_type": "ai"})
    with pytest.raises(ValueError, match="exact blind packet"):
        reconcile(p, inventory, a, b.model_copy(update={"fixture_only": False}))


def test_disagreement_needs_human_resolution_bound_to_both_labels(inventory):
    p = plan(inventory)
    a, b = submissions(p, inventory)
    changed = b.labels[0].model_copy(update={"full_answers": ("126",)})
    b = b.model_copy(update={"labels": (changed, *b.labels[1:])})
    with pytest.raises(ValueError, match="every disagreement"):
        reconcile(p, inventory, a, b)
    old = next(x for x in a.labels if x.qid == changed.qid)
    resolution = OODResolution(
        qid=changed.qid,
        primary_label_sha256=digest(old),
        second_label_sha256=digest(changed),
        final_label=old,
        reviewer="synthetic-adjudicator",
        rationale="synthetic test only",
        human_image_adjudication_attested=True,
    )
    report = reconcile(p, inventory, a, b, [resolution])
    assert report["disagreements"] == 1
    assert next(x for x in report["labels"] if x["qid"] == old.qid)["full_answers"] == ["125"]
    with pytest.raises(ValueError, match="bound to both"):
        reconcile(
            p, inventory, a, b, [resolution.model_copy(update={"primary_label_sha256": HASH})]
        )


def test_inventory_and_duplicate_document_identity(inventory):
    p = plan(inventory)
    clone = p.tasks[1].model_copy(update={"image_sha256": p.tasks[0].image_sha256})
    with pytest.raises(ValueError, match="duplicate OOD images"):
        review_packets(p.model_copy(update={"tasks": (p.tasks[0], clone)}), inventory)
    inventory.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        review_packets(p, inventory)
    with pytest.raises(ValueError, match="must not be empty"):
        review_packets(plan(inventory), inventory)
