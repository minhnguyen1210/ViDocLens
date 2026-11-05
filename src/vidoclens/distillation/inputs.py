"""Materialize question-only Phase 4 inputs without modifying Phase 3 evidence."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.filtering.io import digest, write_model
from vidoclens.filtering.pool import make_pool

COHORT_SHA256 = "db3134d89de01d833080efb7b0dccd6ed99ce3521dcddbecd5187bc20975016a"
G3_EVIDENCE_SHA256 = "386d09fd608d0bace6d3be1ce32ddb983c01ec4cfaf12e4eff40a6e8e8fdaa7a"
G3_PLAN_SHA256 = "2cc060be5c31ff5a6216909039751c2a0f39756db7e5067796fdd8217d62b8a2"


def source_paths(root):
    return (
        root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip",
        root / "data/splits/receiptvqa_containment_v1",
        root / "data/manifests/receiptvqa_ingestion_v1/images.jsonl",
    )


def g3_evidence(root):
    path = root / "artifacts/phase3/g3_report_v1.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    cohort = root / "artifacts/phase3/dev_protocol_v2.json"
    if (
        sha256(path) != G3_EVIDENCE_SHA256
        or report.get("gate") != "G3"
        or report.get("status") != "pass"
        or len(report.get("criteria", {})) != 9
        or not all(report["criteria"].values())
        or report.get("plan_sha256") != G3_PLAN_SHA256
        or sha256(root / "artifacts/phase3/data_v2/manifest.json") != G3_PLAN_SHA256
        or sha256(cohort) != COHORT_SHA256
    ):
        raise ValueError("validated Phase 3 evidence/cohort unavailable or changed")
    return report, cohort


def prepare(root, output):
    root, output = root.resolve(), root.resolve() / output
    report, cohort = g3_evidence(root)
    archive, frozen, inventory = source_paths(root)
    pools = {
        partition: make_pool(
            archive, frozen, inventory, partition, cohort if partition == "dev_select" else None
        )
        for partition in ("dev_select", "train_fit", "audit_holdout")
    }
    output.mkdir(parents=True, exist_ok=False)
    images_dir = output / "images"
    images_dir.mkdir()
    inventory_rows = [
        CorpusImage.model_validate_json(s)
        for s in inventory.read_text(encoding="utf-8").splitlines()
    ]
    by_doc = {r.document_id: r for r in inventory_rows}
    selected = {s.question.document_id for p in pools.values() for s in p.samples}
    image_archive = root / "data/raw/receiptvqa/rotated_images.zip"
    if {by_doc[d].image_archive_sha256 for d in selected} != {sha256(image_archive)}:
        raise ValueError("image archive differs from frozen inventory")
    mapping = {}
    with zipfile.ZipFile(image_archive) as stream:
        for document in sorted(selected):
            row = by_doc[document]
            payload = stream.read(row.archive_member)
            if hashlib.sha256(payload).hexdigest() != row.raw_image_sha256:
                raise ValueError("raw image differs from inventory")
            name = f"images/{row.source_image_id}.jpg"
            (output / name).write_bytes(payload)
            mapping[document] = name
    for partition, pool in pools.items():
        write_model(output / f"{partition}.json", pool)
    write_model(output / "image_map.json", mapping)
    manifest = {
        "protocol": "phase4_inputs_v1",
        "complete": True,
        "g3_sha256": sha256(root / "artifacts/phase3/g3_report_v1.json"),
        "cohort_sha256": sha256(cohort),
        "no_gold_answers": True,
        "image_archive_sha256": sha256(image_archive),
        "pools": {
            k: {
                "sha256": digest(p),
                "qa": len(p.samples),
                "images": len({s.question.document_id for s in p.samples}),
            }
            for k, p in pools.items()
        },
        "files": {p.name: sha256(p) for p in output.glob("*.json")},
    }
    write_model(output / "manifest.json", manifest)
    print(json.dumps(manifest["pools"]), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output)


if __name__ == "__main__":
    main()
