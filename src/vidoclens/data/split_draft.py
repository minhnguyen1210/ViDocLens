"""Build a provisional group split and quarantine; never issue training access."""

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.ingestion import CorpusImage, DraftAssignment, DuplicateGroup, SplitDraft
from vidoclens.contracts.pilot import Phase0PilotManifest
from vidoclens.data.dedup import exact_groups, near_candidates


def ranked(groups: list[str], seed: int, purpose: str) -> list[str]:
    return sorted(
        groups,
        key=lambda value: (hashlib.sha256(f"{seed}:{purpose}:{value}".encode()).hexdigest(), value),
    )


def draft_split(
    images: list[CorpusImage],
    groups: tuple[DuplicateGroup, ...],
    inventory_hash: str,
    seed: int = 42,
) -> SplitDraft:
    by_id = {r.source_image_id: r for r in images}
    image_ids = set(by_id)
    membership = {key: group for group in groups for key in group.source_image_ids}
    if len({g.duplicate_group_id for g in groups}) != len(groups):
        raise ValueError("duplicate group IDs")
    if (
        len(image_ids) != len(images)
        or set(membership) != image_ids
        or sum(len(g.source_image_ids) for g in groups) != len(images)
    ):
        raise ValueError("exact groups must partition the full image inventory")
    if len({r.annotation_archive_sha256 for r in images}) != 1:
        raise ValueError("mixed annotation versions")
    for group in groups:
        actual = {by_id[key].source_split for key in group.source_image_ids}
        if actual != set(group.source_splits):
            raise ValueError("group split metadata is inconsistent")
    pure_train = [g.duplicate_group_id for g in groups if set(g.source_splits) == {"train"}]
    audit_eligible = [
        g.duplicate_group_id
        for g in groups
        if set(g.source_splits) == {"train"} and not g.pilot_exposed
    ]
    audit_count = math.floor(len(pure_train) * 0.1)
    if audit_count > len(audit_eligible):
        raise ValueError("not enough unexposed groups for audit holdout")
    audit = set(ranked(audit_eligible, seed, "audit")[:audit_count])
    dev = [
        g.duplicate_group_id
        for g in groups
        if "dev" in g.source_splits and "test" not in g.source_splits
    ]
    calibration_count = math.floor(len(dev) * 0.3)
    calibrate = set(ranked(dev, seed, "dev_calibrate")[:calibration_count])
    assignments = []
    for row in sorted(images, key=lambda r: r.source_image_id):
        group = membership[row.source_image_id]
        splits = set(group.source_splits)
        reason = None
        if row.source_split == "test":
            partition = "test"
        elif row.source_split == "train" and splits & {"dev", "test"}:
            partition, reason = "quarantine", "train_overlaps_dev_or_test"
        elif row.source_split == "dev" and "test" in splits:
            partition, reason = "quarantine", "dev_overlaps_test"
        elif row.source_split == "train":
            partition = "audit_holdout" if group.duplicate_group_id in audit else "train_fit"
        else:
            partition = "dev_calibrate" if group.duplicate_group_id in calibrate else "dev_select"
        assignments.append(
            DraftAssignment(
                source_image_id=row.source_image_id,
                source_split=row.source_split,
                duplicate_group_id=group.duplicate_group_id,
                partition=partition,
                quarantine_reason=reason,
                pilot_exposed=group.pilot_exposed,
            )
        )
    training_groups = ranked(sorted(set(pure_train) - audit), seed, "nested_gold")
    budgets = {
        str(k): tuple(training_groups[: math.floor(len(training_groups) * k / 100)])
        for k in (5, 10, 25, 100)
    }
    return SplitDraft(
        annotation_archive_sha256=images[0].annotation_archive_sha256,
        image_inventory_sha256=inventory_hash,
        seed=seed,
        assignments=tuple(assignments),
        gold_group_sets=budgets,
    )


def build(inventory_dir: Path, pilot_file: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("dedup output must be a new directory")
    summary = json.loads((inventory_dir / "summary.json").read_text(encoding="utf-8"))
    inventory = inventory_dir / "images.jsonl"
    inventory_hash = sha256(inventory)
    if summary.get("status") != "pass" or summary["image_inventory_sha256"] != inventory_hash:
        raise ValueError("inventory incomplete or checksum mismatch")
    images = [
        CorpusImage.model_validate_json(line)
        for line in inventory.read_text(encoding="utf-8").splitlines()
    ]
    if len(images) != summary["images"]:
        raise ValueError("inventory count mismatch")
    pilot = Phase0PilotManifest.model_validate_json(pilot_file.read_text(encoding="utf-8"))
    by_document = {row.document_id: row for row in images}
    pilot_ids = set()
    for row in pilot.pilot:
        image = by_document.get(row.document_id)
        if (
            image is None
            or image.raw_image_sha256 != row.image_sha256
            or image.source_split != "train"
        ):
            raise ValueError("pilot provenance not matched to inventory")
        pilot_ids.add(image.source_image_id)
    groups = exact_groups(images, pilot_ids)
    draft = draft_split(images, groups, inventory_hash)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "exact_groups.json", {"groups": [g.model_dump() for g in groups]})
    candidates, cross = 0, 0
    with (output / "near_duplicate_candidates.jsonl").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        for item in near_candidates(images, groups):
            stream.write(item.model_dump_json() + "\n")
            candidates += 1
            cross += item.crosses_official_splits
    write_json(output / "split_draft.json", draft.model_dump())
    qa_by_id = {r.source_image_id: r.qa_count for r in images}
    counts = Counter(a.partition for a in draft.assignments)
    qa_counts = Counter()
    for row in draft.assignments:
        qa_counts[row.partition] += qa_by_id[row.source_image_id]
    for source in (Path(__file__), Path(__file__).with_name("dedup.py")):
        with (output / ("source_" + source.name)).open("xb") as stream:
            stream.write(source.read_bytes())
    report = {
        "status": "draft_ready_review_required",
        "created_utc": datetime.now(UTC).isoformat(),
        "images": len(images),
        "exact_groups": len(groups),
        "duplicate_groups": sum(len(g.source_image_ids) > 1 for g in groups),
        "cross_split_exact_groups": sum(len(g.source_splits) > 1 for g in groups),
        "pilot_exposed_groups": sum(g.pilot_exposed for g in groups),
        "near_candidates": candidates,
        "near_candidates_cross_official_splits": cross,
        "candidate_thresholds": {"phash64": 6, "center_crop_phash64": 4},
        "partition_image_counts": dict(counts),
        "partition_qa_counts": dict(qa_counts),
        "gold_group_counts": {k: len(v) for k, v in draft.gold_group_sets.items()},
        "image_inventory_sha256": inventory_hash,
        "pilot_manifest_sha256": sha256(pilot_file),
        "split_draft_sha256": sha256(output / "split_draft.json"),
        "near_queue_sha256": sha256(output / "near_duplicate_candidates.jsonl"),
        "training_allowed": False,
        "final_split_frozen": False,
        "question_type_stratification": False,
        "source_scope": ["ReceiptVQA official rotated archive"],
        "limitations": [
            "near candidates require visual review",
            "additional OCR/feature matching for crop/rotation remains",
            "other data sources not ingested",
            "all gold access remains disabled by this draft",
        ],
    }
    write_json(output / "summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory-dir", "pilot", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build(args.inventory_dir, args.pilot, args.output)
    except Exception as error:
        parser.exit(1, f"Dedup/draft failed ({type(error).__name__}); no training grant.\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
