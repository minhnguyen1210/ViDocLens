"""Question-only distributions and an independent overlap audit of a frozen split."""

import argparse
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.ingestion import (
    CorpusImage,
    FeatureCandidate,
    FeatureFingerprint,
    NearDuplicateCandidate,
)
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_questions, load_silver_questions, load_training_examples


def question_type(question: str) -> str:
    text = unicodedata.normalize("NFC", question).lower()
    for kind, words in (
        ("address", ("địa chỉ", "đường nào")),
        ("time", ("mấy giờ", "thời gian", "ngày nào", "ngày tháng")),
        ("total", ("tổng tiền", "tổng cộng", "thanh toán")),
        ("merchant", ("cửa hàng", "tên quán", "nhà hàng", "siêu thị")),
        ("quantity", ("số lượng", "bao nhiêu sản phẩm")),
        ("item_price", ("đơn giá", "giá tiền", "bao nhiêu tiền")),
        ("product", ("sản phẩm", "mặt hàng", "món")),
    ):
        if any(word in text for word in words):
            return kind
    return "other"


def run(
    annotations: Path,
    inventory: Path,
    split_dir: Path,
    dedup_dir: Path,
    feature_dir: Path,
    output: Path,
):
    plan = load_frozen_plan(split_dir, 10)
    if sha256(inventory) != plan.image_inventory_sha256:
        raise ValueError("inventory/split mismatch")
    images = [CorpusImage.model_validate_json(l) for l in inventory.read_text().splitlines()]
    image_hashes = {r.source_image_id: r.raw_image_sha256 for r in images}
    frozen = json.loads((split_dir / "summary.json").read_text(encoding="utf-8"))
    if (
        sha256(dedup_dir / "near_duplicate_candidates.jsonl") != frozen["near_queue_sha256"]
        or sha256(feature_dir / "candidates.jsonl") != frozen["feature_queue_sha256"]
    ):
        raise ValueError("candidate sources differ from frozen split")
    by_id = {a.source_image_id: a for a in plan.assignments}
    if set(by_id) != {r.source_image_id for r in images} or len(by_id) != len(images):
        raise ValueError("split does not cover inventory exactly")
    unique_groups = defaultdict(set)
    for a in plan.assignments:
        if a.partition != "quarantine":
            unique_groups[a.duplicate_group_id].add(a.partition)
    if any(len(p) > 1 for p in unique_groups.values()):
        raise ValueError("cross-partition leakage")
    for l in (feature_dir / "features.jsonl").read_text().splitlines():
        row = FeatureFingerprint.model_validate_json(l)
        if row.raw_image_sha256 != image_hashes[row.source_image_id]:
            raise ValueError("feature image provenance mismatch")
    pairs = set()
    for directory, name, model in (
        (dedup_dir, "near_duplicate_candidates.jsonl", NearDuplicateCandidate),
        (feature_dir, "candidates.jsonl", FeatureCandidate),
    ):
        for line in (directory / name).read_text().splitlines():
            r = model.model_validate_json(line)
            pairs.add((r.left_image_id, r.right_image_id))
    if any(by_id[a].duplicate_group_id != by_id[b].duplicate_group_id for a, b in pairs):
        raise ValueError("uncontained candidate edge")
    distribution = defaultdict(Counter)
    for source in ("train", "dev"):
        for q in load_questions(annotations, split=source):
            distribution[by_id[q.source_image_id].partition][question_type(q.question_raw)] += 1
    gold = load_training_examples(annotations, plan)
    silver = load_silver_questions(annotations, plan)
    if {r.question.document_id for r in gold} & {r.document_id for r in silver}:
        raise ValueError("gold and silver groups overlap")
    allowed = {a.source_image_id for a in plan.assignments if a.partition == "train_fit"}
    if any(r.source_image_id not in allowed for r in silver) or any(
        r.question.source_image_id not in allowed for r in gold
    ):
        raise ValueError("nontraining data exposed")
    if any("answer" in key or "gold" in key for r in silver for key in r.model_dump()):
        raise ValueError("gold field leaked to silver inputs")
    # Test remains unavailable before the final frozen experiment suite.
    try:
        load_questions(annotations, split="test")
    except PermissionError:
        pass
    else:
        raise ValueError("test reader unexpectedly enabled")
    counts = Counter()
    qa = Counter()
    for r in images:
        p = by_id[r.source_image_id].partition
        counts[p] += 1
        qa[p] += r.qa_count
    report = {
        "status": "pass",
        "images": len(images),
        "qa": sum(qa.values()),
        "uncontained_edges": 0,
        "candidate_pairs": len(pairs),
        "cross_partition_components": 0,
        "partition_images": dict(counts),
        "partition_qa": dict(qa),
        "gold_g10_training_qa": len(gold),
        "silver_question_only_qa": len(silver),
        "test_gold_read": False,
        "silver_contains_gold_fields": False,
        "question_heuristic_distribution": {k: dict(v) for k, v in distribution.items()},
        "question_taxonomy_source": "unvalidated question-only keywords, descriptive not strata gold",
        "split_summary_sha256": sha256(split_dir / "summary.json"),
        "annotations_sha256": sha256(annotations),
    }
    write_json(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "question_heuristic_distribution"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("annotations", "inventory", "split-dir", "dedup-dir", "feature-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
