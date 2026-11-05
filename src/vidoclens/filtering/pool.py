"""Build a label-free G10 pool from existing frozen artifacts, without changing splits."""

import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.silver import SilverPool, SilverSample
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_questions, load_silver_questions
from vidoclens.filtering.io import digest


def make_pool(
    archive: Path,
    frozen: Path,
    inventory: Path,
    partition: str,
    evaluation_cohort: Path | None = None,
) -> SilverPool:
    if partition not in {"train_fit", "dev_select", "audit_holdout"}:
        raise PermissionError("silver tooling cannot open test/OOD/calibration/quarantine")
    cohort = None
    if evaluation_cohort is not None:
        if partition != "dev_select":
            raise PermissionError("cohort selection cannot reduce training or audit population")
        cohort = json.loads(evaluation_cohort.read_text(encoding="utf-8"))
        if (
            cohort.get("protocol") != "phase3_dev_v1"
            or cohort.get("test_or_ood_used") is not False
            or not cohort.get("qids")
            or len(set(cohort["qids"])) != len(cohort["qids"])
            or set(cohort.get("groups", {})) != set(cohort["qids"])
        ):
            raise ValueError("invalid frozen Phase3 evaluation cohort")
    plan = load_frozen_plan(frozen, 10)
    inventory_hash = sha256(inventory)
    if inventory_hash != plan.image_inventory_sha256 or sha256(archive) != plan.archive_sha256:
        raise ValueError("pool inputs do not match the frozen plan")
    images = [
        CorpusImage.model_validate_json(line)
        for line in inventory.read_text(encoding="utf-8").splitlines()
    ]
    by_image = {r.source_image_id: r for r in images}
    assignments = {a.source_image_id: a for a in plan.assignments}
    if len(by_image) != len(images) or set(by_image) != set(assignments):
        raise ValueError("inventory must exactly cover frozen membership")
    questions = load_questions(archive, split="dev" if partition == "dev_select" else "train")
    silver_ids = (
        {q.qid for q in load_silver_questions(archive, plan)} if partition == "train_fit" else None
    )
    samples, gold = [], []
    for q in questions:
        a, im = assignments[q.source_image_id], by_image[q.source_image_id]
        if (
            im.document_id != q.document_id
            or im.annotation_archive_sha256 != plan.archive_sha256
            or im.source_split != q.source_split
            or a.source_split != q.source_split
            or im.annotation_filename != q.filename
        ):
            raise ValueError("question/image/frozen split identity mismatch")
        if a.partition != partition:
            continue
        row = SilverSample(
            question=q,
            duplicate_group_id=a.duplicate_group_id,
            image_sha256=im.raw_image_sha256,
        )
        if partition == "train_fit" and a.gold_for_training:
            gold.append(row)
        elif silver_ids is None or q.qid in silver_ids:
            samples.append(row)
    if cohort is not None:
        by_qid = {s.question.qid: s for s in samples}
        if not set(cohort["qids"]) <= by_qid.keys() or any(
            by_qid[qid].duplicate_group_id != group for qid, group in cohort["groups"].items()
        ):
            raise ValueError("evaluation cohort differs from frozen dev membership")
        documents = {by_qid[qid].question.document_id for qid in cohort["qids"]}
        if {s.question.qid for s in samples if s.question.document_id in documents} != set(
            cohort["qids"]
        ):
            raise ValueError("cohort must include all questions of each selected receipt")
        samples = [s for s in samples if s.question.qid in cohort["groups"]]
    return SilverPool(
        partition=partition,
        archive_sha256=plan.archive_sha256,
        access_plan_sha256=digest(plan),
        inventory_sha256=inventory_hash,
        evaluation_cohort_sha256=sha256(evaluation_cohort) if evaluation_cohort else None,
        samples=tuple(sorted(samples, key=lambda r: r.question.qid)),
        gold_samples=tuple(sorted(gold, key=lambda r: r.question.qid)),
    )
