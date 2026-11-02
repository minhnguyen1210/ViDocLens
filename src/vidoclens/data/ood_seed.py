"""Import licensed Commons seed images and contain cross-source duplicate candidates."""

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

from vidoclens.common.pilot import environment, sha256, write_json
from vidoclens.contracts.ai_review import OODSeedDocument
from vidoclens.contracts.ingestion import CorpusImage, FeatureFingerprint
from vidoclens.data.feature_candidates import image_features
from vidoclens.data.images import canonical_image, fingerprints, pixel_sha256

SOURCE_NOTES = {
    171575050: (
        "postal_remittance_sample",
        ("source", "postal_layout", "masked_fields"),
        ("Source describes a sample; masked private fields must remain unknown.",),
    ),
    59349747: (
        "transport_fee_blank_form",
        ("source", "preprinted_form", "blank_fields"),
        ("Blank form with a preprinted fee, not evidence of a completed payment.",),
    ),
    113371922: (
        "restaurant_receipt",
        ("source", "english_text", "cropped_header"),
        (
            "Receipt photographed in Vietnam; visible text is English.",
            "Restaurant identity is outside the visible image; no metadata-derived answers.",
        ),
    ),
}


def local_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes project root")
    return path


def candidate_reasons(left: dict, right: dict) -> tuple[list[str], dict]:
    """Prespecified thresholds, no labels or semantic acceptance of near matches."""

    def distance(a, b):
        return (int(a, 16) ^ int(b, 16)).bit_count()

    distances = {
        "full": distance(left["phash64"], right["phash64"]),
        "crop80": distance(left["center_crop_phash64"], right["center_crop_phash64"]),
        "rotation": min(
            distance(a, b) for a in left["phash_rotations"] for b in right["phash_rotations"]
        ),
        "crop60": min(
            distance(left["crop60_phash"], right["crop60_phash"]),
            distance(left["crop60_phash"], right["phash_rotations"][0]),
            distance(left["phash_rotations"][0], right["crop60_phash"]),
        ),
        "gradient": min(
            distance(a, b) for a in left["gradient_rotations"] for b in right["gradient_rotations"]
        ),
    }
    reasons = [k for k in ("raw_image_sha256", "canonical_pixel_sha256") if left[k] == right[k]]
    reasons.extend(
        k
        for k, threshold in {"full": 6, "crop80": 4, "rotation": 4, "crop60": 2}.items()
        if distances[k] <= threshold
    )
    ones = [int(r["gradient_rotations"][0], 16).bit_count() for r in (left, right)]
    if distances["gradient"] <= 2 and all(8 <= n <= 120 for n in ones):
        reasons.append("gradient")
    return reasons, distances


def import_document(root: Path, number: int) -> tuple[OODSeedDocument, dict]:
    raw = Path(f"data/raw/commons_ood_seed_v1/commons_{number}.jpg")
    processed = Path(f"data/processed/commons_ood_seed_v1/commons_{number}.png")
    metadata = Path(f"data/raw/commons_ood_seed_v1/metadata_{number}.json")
    pages = json.loads((root / metadata).read_text(encoding="utf-8"))["query"]["pages"]
    if len(pages) != 1:
        raise ValueError("one source page is required")
    page = next(iter(pages.values()))
    info = page["imageinfo"][0]
    ext = info["extmetadata"]
    payload = (root / raw).read_bytes()
    if len(payload) != info["size"] or hashlib.sha1(payload).hexdigest() != info["sha1"]:
        raise ValueError("download differs from Commons metadata")
    canonical, _ = canonical_image(payload)
    actual, _ = canonical_image((root / processed).read_bytes())
    if pixel_sha256(actual) != pixel_sha256(canonical):
        raise ValueError("processed image changed canonical pixels")
    kind, axes, caveats = SOURCE_NOTES[page["pageid"]]
    raw_hash = sha256(root / raw)
    revision = page["revisions"][0]["revid"]
    document = OODSeedDocument(
        document_id=f"commons:{page['pageid']}:{raw_hash}",
        page_id=page["pageid"],
        page_revision=revision,
        source_url=info["descriptionurl"],
        original_url=info["url"].split("?")[0],
        author_credit=html.unescape(re.sub("<[^>]+>", "", ext["Artist"]["value"])),
        license_id=ext["LicenseShortName"]["value"],
        license_url=ext["LicenseUrl"]["value"],
        rights_evidence_id=f"commons:{page['pageid']}:revision:{revision}",
        metadata_path=metadata.as_posix(),
        metadata_sha256=sha256(root / metadata),
        raw_path=raw.as_posix(),
        image_path=processed.as_posix(),
        raw_image_sha256=raw_hash,
        processed_image_sha256=sha256(root / processed),
        canonical_pixel_sha256=pixel_sha256(canonical),
        width=canonical.width,
        height=canonical.height,
        document_kind=kind,
        shift_axes=axes,
        source_caveats=caveats,
        partition="ood_seed",
    )
    return document, {
        **fingerprints(payload),
        **image_features(payload),
        "document_id": document.document_id,
    }


def run(root: Path, output: Path):
    inventory = root / "data/manifests/receiptvqa_ingestion_v1/images.jsonl"
    features = root / "data/manifests/receiptvqa_features_v1/features.jsonl"
    inventory_summary = json.loads(inventory.with_name("summary.json").read_text())
    feature_summary = json.loads(features.with_name("summary.json").read_text())
    if inventory_summary["image_inventory_sha256"] != sha256(inventory) or feature_summary[
        "features_sha256"
    ] != sha256(features):
        raise ValueError("frozen ReceiptVQA evidence changed")
    rows = [CorpusImage.model_validate_json(line) for line in inventory.read_text().splitlines()]
    extra = [
        FeatureFingerprint.model_validate_json(line) for line in features.read_text().splitlines()
    ]
    by_id = {r.source_image_id: r for r in extra}
    if len(by_id) != len(rows) or len(extra) != len(rows):
        raise ValueError("incomplete feature inventory")
    corpus = []
    for row in rows:
        feature = by_id[row.source_image_id]
        if row.raw_image_sha256 != feature.raw_image_sha256:
            raise ValueError("feature raw hash mismatch")
        corpus.append({**row.model_dump(), **feature.model_dump()})
    documents, edges, minima, seed_features = [], [], {}, []
    for n in (1, 2, 3):
        document, feature = import_document(root, n)
        closest = {k: 129 for k in ("full", "crop80", "rotation", "crop60", "gradient")}
        for other in corpus + seed_features:
            reasons, distances = candidate_reasons(feature, other)
            closest = {k: min(v, distances[k]) for k, v in closest.items()}
            if reasons:
                edges.append(
                    {
                        "left": document.document_id,
                        "right": other["document_id"],
                        "reasons": reasons,
                        "distances": distances,
                        "status": "uncertain_quarantine",
                    }
                )
        seed_features.append(feature)
        documents.append(document)
        minima[document.document_id] = closest
    affected = {e[k] for e in edges for k in ("left", "right")}
    documents = [
        d.model_copy(update={"partition": "quarantine"}) if d.document_id in affected else d
        for d in documents
    ]
    output.mkdir(parents=True, exist_ok=False)
    (output / "documents.jsonl").write_text(
        "".join(d.model_dump_json() + "\n" for d in documents), encoding="utf-8"
    )
    write_json(
        output / "overlap.json",
        {
            "edges": edges,
            "minimum_distances": minima,
            "compared_receiptvqa_images": len(rows),
            "seed_pair_comparisons": 3,
            "receiptvqa_pair_comparisons": len(rows) * len(documents),
        },
    )
    frozen = root / "data/splits/receiptvqa_containment_v1"
    write_json(
        output / "graph_extension.json",
        {
            "base_graph_path": (frozen / "containment_groups.json").relative_to(root).as_posix(),
            "base_graph_sha256": sha256(frozen / "containment_groups.json"),
            "nodes": [d.document_id for d in documents],
            "candidate_edges": edges,
            "policy": (
                "isolate every seed node touching an unresolved edge; "
                "base graph/splits remain immutable"
            ),
            "permissions": {d.document_id: d.partition for d in documents},
        },
    )
    write_json(output / "environment.json", environment())
    (output / "source.py").write_bytes(Path(__file__).read_bytes())
    report = {
        "status": "pass" if not edges else "quarantine",
        "images": len(documents),
        "eligible_images": sum(d.partition == "ood_seed" for d in documents),
        "candidate_edges": len(edges),
        "inventory_sha256": sha256(inventory),
        "features_sha256": sha256(features),
        "documents_sha256": sha256(output / "documents.jsonl"),
        "overlap_sha256": sha256(output / "overlap.json"),
        "graph_extension_sha256": sha256(output / "graph_extension.json"),
        "human_verified": False,
        "training_allowed": False,
        "final_benchmark": False,
    }
    write_json(output / "summary.json", report)
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.output)


if __name__ == "__main__":
    main()
