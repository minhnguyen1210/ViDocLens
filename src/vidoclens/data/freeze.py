"""Freeze conservative leakage constraints, never assert uncertain receipts are identical."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.dataset import ReceiptAccessPlan, ReceiptAssignment
from vidoclens.contracts.ingestion import (
    CorpusImage, DuplicateGroup, FeatureCandidate, NearDuplicateCandidate,
)
from vidoclens.contracts.pilot import Phase0PilotManifest
from vidoclens.data.dedup import exact_groups
from vidoclens.data.split_draft import draft_split


def containment_groups(images, edges, pilot_ids):
    by_id = {r.source_image_id: r for r in images}
    if len(by_id) != len(images):
        raise ValueError("duplicate inventory IDs")
    parents = {i: i for i in by_id}

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def join(a, b):
        if a not in parents or b not in parents:
            raise ValueError("candidate ID missing from inventory")
        a, b = root(a), root(b)
        parents[max(a, b)] = min(a, b)

    for group in exact_groups(images, pilot_ids):
        for i in group.source_image_ids:
            join(i, group.source_image_ids[0])
    for a, b in edges:
        if a >= b:
            raise ValueError("candidate IDs must be ordered and distinct")
        join(a, b)
    members = defaultdict(list)
    for i in sorted(by_id):
        members[root(i)].append(i)
    groups = []
    for ids in members.values():
        digest = hashlib.sha256(
            json.dumps([by_id[i].document_id for i in ids]).encode()
        ).hexdigest()
        groups.append(
            DuplicateGroup(
                duplicate_group_id="receiptvqa-containment:" + digest,
                source_image_ids=tuple(ids),
                source_splits=tuple(sorted({by_id[i].source_split for i in ids})),
                grouping_evidence="conservative_candidate_component",
                pilot_exposed=bool(set(ids) & pilot_ids),
            )
        )
    return tuple(sorted(groups, key=lambda g: g.duplicate_group_id))


def access_plan(draft, budget, graph_hash):
    selected = set(draft.gold_group_sets[str(budget)])
    return ReceiptAccessPlan(
        archive_sha256=draft.annotation_archive_sha256,
        grouping_status="conservative_candidate_graph",
        image_inventory_sha256=draft.image_inventory_sha256,
        candidate_graph_sha256=graph_hash,
        assignments=tuple(
            ReceiptAssignment(
                source_image_id=a.source_image_id,
                source_split=a.source_split,
                duplicate_group_id=a.duplicate_group_id,
                partition=a.partition,
                gold_for_training=a.partition == "train_fit" and a.duplicate_group_id in selected,
            )
            for a in draft.assignments
        ),
    )


def load_frozen_plan(directory: Path, budget: int = 10):
    if budget not in {5, 10, 25, 100}:
        raise ValueError("unregistered gold budget")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "frozen_conservative" or summary.get("uncontained_edges") != 0:
        raise ValueError("split is not frozen with complete containment")
    required = {"containment_groups.json", "partition_membership.json"} | {
        f"access_g{k}.json" for k in (5, 10, 25, 100)
    }
    if not required <= summary["files"].keys():
        raise ValueError("frozen split is missing required checksums")
    for name, digest in summary["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or sha256(path) != digest:
            raise ValueError("frozen split evidence checksum mismatch")
    plan = ReceiptAccessPlan.model_validate_json(
        (directory / f"access_g{budget}.json").read_text(encoding="utf-8")
    )
    if plan.candidate_graph_sha256 != summary["files"]["containment_groups.json"]:
        raise ValueError("plan not bound to containment graph")
    graph = json.loads((directory / "containment_groups.json").read_text(encoding="utf-8"))
    membership = {i: g["duplicate_group_id"] for g in graph["groups"] for i in g["source_image_ids"]}
    if membership != {a.source_image_id: a.duplicate_group_id for a in plan.assignments}:
        raise ValueError("plan membership does not match frozen graph")
    return plan


def run(inventory_dir: Path, dedup_dir: Path, feature_dir: Path, pilot: Path, output: Path):
    inv = inventory_dir / "images.jsonl"
    ingestion = json.loads((inventory_dir / "summary.json").read_text())
    ds = json.loads((dedup_dir / "summary.json").read_text())
    fs = json.loads((feature_dir / "summary.json").read_text())
    ih = sha256(inv)
    if (
        ingestion["status"] != "pass"
        or fs["status"] != "pass"
        or any(
            v != ih
            for v in (
                ingestion["image_inventory_sha256"],
                ds["image_inventory_sha256"],
                fs["inventory_sha256"],
            )
        )
    ):
        raise ValueError("inventory provenance mismatch")
    queue = dedup_dir / "near_duplicate_candidates.jsonl"
    fq = feature_dir / "candidates.jsonl"
    if (
        sha256(queue) != ds["near_queue_sha256"]
        or sha256(fq) != fs["candidates_sha256"]
        or sha256(pilot) != ds["pilot_manifest_sha256"]
    ):
        raise ValueError("candidate or pilot checksum mismatch")
    images = [CorpusImage.model_validate_json(line) for line in inv.read_text().splitlines()]
    if len(images) != ingestion["images"] or len(images) != fs["images"]:
        raise ValueError("inventory count mismatch")
    pp = Phase0PilotManifest.model_validate_json(pilot.read_text(encoding="utf-8"))
    by_doc = {r.document_id: r for r in images}
    pilot_ids = set()
    for row in pp.pilot:
        ref = by_doc[row.document_id]
        if ref.raw_image_sha256 != row.image_sha256 or ref.source_split != "train":
            raise ValueError("invalid pilot provenance")
        pilot_ids.add(ref.source_image_id)
    edges = set()
    for line in queue.read_text().splitlines():
        r = NearDuplicateCandidate.model_validate_json(line)
        edges.add((r.left_image_id, r.right_image_id))
    for line in fq.read_text().splitlines():
        r = FeatureCandidate.model_validate_json(line)
        edges.add((r.left_image_id, r.right_image_id))
    groups = containment_groups(images, edges, pilot_ids)
    draft = draft_split(images, groups, ih)
    membership = {i: g.duplicate_group_id for g in groups for i in g.source_image_ids}
    if any(membership[a] != membership[b] for a, b in edges):
        raise ValueError("candidate edge is not contained")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "containment_groups.json", {"groups": [g.model_dump() for g in groups]})
    graph_hash = sha256(output / "containment_groups.json")
    write_json(output / "partition_membership.json", draft.model_dump())
    for k in (5, 10, 25, 100):
        write_json(output / f"access_g{k}.json", access_plan(draft, k, graph_hash).model_dump())
    (output / "source_freeze.py").write_bytes(Path(__file__).read_bytes())
    (output / "source_split_draft.py").write_bytes(
        Path(__file__).with_name("split_draft.py").read_bytes()
    )
    image_counts, qa_counts = Counter(), Counter()
    qa = {r.source_image_id: r.qa_count for r in images}
    for a in draft.assignments:
        image_counts[a.partition] += 1
        qa_counts[a.partition] += qa[a.source_image_id]
    files = {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()}
    report = {
        "status": "frozen_conservative",
        "created_utc": datetime.now(UTC).isoformat(),
        "semantic_review_complete": False,
        "training_allowed": True,
        "candidate_pairs_contained": len(edges),
        "uncontained_edges": 0,
        "containment_components": len(groups),
        "largest_component": max(len(g.source_image_ids) for g in groups),
        "partition_image_counts": dict(image_counts),
        "partition_qa_counts": dict(qa_counts),
        "gold_group_counts": {k: len(v) for k, v in draft.gold_group_sets.items()},
        "inventory_sha256": ih,
        "near_queue_sha256": sha256(queue),
        "feature_queue_sha256": sha256(fq),
        "pilot_sha256": sha256(pilot),
        "files": files,
        "limitations": [
            "uncertain pairs are containment constraints, not proven duplicates",
            "not exhaustive for arbitrary recaptures/crops",
            "ReceiptVQA only",
            "no source question taxonomy; deterministic group ranking, not stratification",
        ],
    }
    write_json(output / "summary.json", report)
    for k in (5, 10, 25, 100):
        load_frozen_plan(output, k)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory-dir", "dedup-dir", "feature-dir", "pilot", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
