"""Label-free rotation/crop/gradient candidates; every edge remains uncertain."""

import argparse
import hashlib
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vidoclens.common.pilot import environment, sha256, write_json
from vidoclens.contracts.ingestion import CorpusImage, FeatureCandidate, FeatureFingerprint
from vidoclens.data.images import canonical_image, phash64

PROTOCOL = {
    "version": "rotation_crop_gradient_v1",
    "rotation_phash_distance": 4,
    "center_crop_fraction": 0.6,
    "crop_phash_distance": 2,
    "gradient_dhash128_distance": 2,
    "gradient_min_ones": 8,
    "semantic_duplicate_decision": False,
}


def gradient_hash(image) -> str:
    import numpy as np
    from PIL import Image

    horizontal = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    vertical = np.asarray(image.convert("L").resize((8, 9), Image.Resampling.LANCZOS))
    bits = np.concatenate(
        (
            (horizontal[:, 1:] > horizontal[:, :-1]).ravel(),
            (vertical[1:, :] > vertical[:-1, :]).ravel(),
        )
    )
    return np.packbits(bits).tobytes().hex()


def features(item: tuple[CorpusImage, bytes]) -> dict:
    row, payload = item
    if hashlib.sha256(payload).hexdigest() != row.raw_image_sha256:
        raise ValueError("raw image changed")
    return {
        "source_image_id": row.source_image_id,
        "raw_image_sha256": row.raw_image_sha256,
        **image_features(payload),
    }


def image_features(payload: bytes) -> dict:
    """Same label-free transform for ReceiptVQA and external source audits."""
    image, _ = canonical_image(payload)
    # Resize once before the small fingerprints, bounded CPU cost, no saved derivative.
    image.thumbnail((512, 512))
    views = [image.rotate(angle, expand=True) for angle in (0, 90, 180, 270)]
    w, h = image.size
    crop = image.crop((w // 5, h // 5, w - w // 5, h - h // 5))
    return {
        "phash_rotations": [phash64(v) for v in views],
        "crop60_phash": phash64(crop),
        "gradient_rotations": [gradient_hash(v) for v in views],
    }


def candidate_pairs(rows):
    import numpy as np

    ordered = sorted(rows, key=lambda r: r["source_image_id"])
    ph = np.array([[int(v, 16) for v in r["phash_rotations"]] for r in ordered], dtype=np.uint64)
    crop = np.array([int(r["crop60_phash"], 16) for r in ordered], dtype=np.uint64)
    dh = np.array(
        [[[int(v[:16], 16), int(v[16:], 16)] for v in r["gradient_rotations"]] for r in ordered],
        dtype=np.uint64,
    )
    for i, left in enumerate(ordered[:-1]):
        rest = slice(i + 1, None)
        rot = np.bitwise_count(ph[rest, 0, None] ^ ph[i, None, :]).min(axis=1)
        cd = np.minimum(
            np.bitwise_count(crop[rest] ^ crop[i]),
            np.minimum(
                np.bitwise_count(ph[rest, 0] ^ crop[i]), np.bitwise_count(crop[rest] ^ ph[i, 0])
            ),
        )
        dd = np.bitwise_count(dh[rest, 0, None, :] ^ dh[i, None, :, :]).sum(axis=2).min(axis=1)
        ones_left = int(np.bitwise_count(dh[i, 0]).sum())
        ones_right = np.bitwise_count(dh[rest, 0]).sum(axis=1)
        gradient = (dd <= 2) & (ones_right >= 8) & (ones_right <= 120) & (8 <= ones_left <= 120)
        for off in np.flatnonzero((rot <= 4) | (cd <= 2) | gradient):
            yield {
                "left_image_id": left["source_image_id"],
                "right_image_id": ordered[i + 1 + int(off)]["source_image_id"],
                "rotation_phash_distance": int(rot[off]),
                "crop_phash_distance": int(cd[off]),
                "gradient_distance": int(dd[off]),
                "review_status": "uncertain",
            }


def run(inventory_dir: Path, archive: Path, output: Path, workers: int = 4):
    if not 1 <= workers <= 8:
        raise ValueError("workers must be 1..8")
    inventory = inventory_dir / "images.jsonl"
    summary = json.loads((inventory_dir / "summary.json").read_text())
    if summary["status"] != "pass" or summary["image_inventory_sha256"] != sha256(inventory):
        raise ValueError("inventory integrity failed")
    rows = [CorpusImage.model_validate_json(line) for line in inventory.read_text().splitlines()]
    if len(rows) != summary["images"] or {r.image_archive_sha256 for r in rows} != {
        sha256(archive)
    }:
        raise ValueError("inventory count/archive mismatch")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "protocol.json", PROTOCOL)
    write_json(output / "environment.json", environment())
    (output / "source.py").write_bytes(Path(__file__).read_bytes())
    values = []
    with zipfile.ZipFile(archive) as z, ThreadPoolExecutor(max_workers=workers) as pool:
        with (output / "features.jsonl").open("x", encoding="utf-8") as stream:
            for start in range(0, len(rows), workers * 2):
                batch = [(r, z.read(r.archive_member)) for r in rows[start : start + workers * 2]]
                for item in pool.map(features, batch):
                    validated = FeatureFingerprint.model_validate(item)
                    stream.write(validated.model_dump_json() + "\n")
                    values.append(item)
                if start % 800 == 0:
                    print(f"fingerprints {len(values)}/{len(rows)}", flush=True)
    count = 0
    with (output / "candidates.jsonl").open("x", encoding="utf-8") as stream:
        for pair in candidate_pairs(values):
            stream.write(FeatureCandidate.model_validate(pair).model_dump_json() + "\n")
            count += 1
    report = {
        "status": "pass",
        "images": len(values),
        "candidates": count,
        "inventory_sha256": sha256(inventory),
        "features_sha256": sha256(output / "features.jsonl"),
        "candidates_sha256": sha256(output / "candidates.jsonl"),
        "protocol_sha256": sha256(output / "protocol.json"),
    }
    write_json(output / "summary.json", report)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory-dir", "archive", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.inventory_dir, args.archive, args.output)


if __name__ == "__main__":
    main()
