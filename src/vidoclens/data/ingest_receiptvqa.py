"""Audit ReceiptVQA image bytes and emit a label-free, immutable image inventory."""

import argparse
import csv
import io
import json
import stat
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from vidoclens.common.pilot import environment, sha256, write_json
from vidoclens.contracts.dataset import ReceiptQuestion
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.data.audit_receiptvqa import PREFIX, SPLITS, audit_archive
from vidoclens.data.images import MAX_IMAGE_BYTES, TRANSFORM, fingerprints


def annotation_metadata(path: Path) -> tuple[str, list[dict], dict]:
    report = audit_archive(path)
    if report["status"] != "pass":
        raise ValueError("annotation structural audit failed")
    records = {}
    with zipfile.ZipFile(path) as archive:
        for split in SPLITS:
            # Only identifiers/filenames/counts leave this structural reader.
            # No question/answer strings from test are inspected for model decisions.
            with archive.open(f"{PREFIX}ReceiptVQA_{split}.csv") as member:
                reader = csv.DictReader(io.TextIOWrapper(member, encoding="utf-8-sig", newline=""))
                for row in reader:
                    image_id, filename = int(row["image_id"]), row["filename"]
                    ReceiptQuestion.safe_filename(filename)
                    if image_id not in records:
                        records[image_id] = {
                            "source_image_id": image_id,
                            "source_split": split,
                            "annotation_filename": filename,
                            "qa_count": 0,
                        }
                    record = records[image_id]
                    if (record["source_split"], record["annotation_filename"]) != (split, filename):
                        raise ValueError("ambiguous annotation image identity")
                    record["qa_count"] += 1
    return (
        report["archive_sha256"],
        sorted(records.values(), key=lambda r: r["source_image_id"]),
        report,
    )


def match_members(archive: zipfile.ZipFile, records: list[dict]) -> dict[str, tuple[str, str]]:
    entries = archive.infolist()
    if len(entries) > 100_001 or sum(e.file_size for e in entries) > 24 * 1024**3:
        raise ValueError("image archive exceeds inventory limits")
    names, by_name, by_stem = set(), {}, defaultdict(list)
    for entry in entries:
        name = entry.filename
        original_name = entry.orig_filename
        path = PurePosixPath(name)
        if (
            original_name != name
            or name in names
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or ":" in name
            or "\0" in name
        ):
            raise ValueError("unsafe or duplicated image ZIP path")
        names.add(name)
        if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
            raise ValueError("symlink/encrypted image ZIP member")
        if entry.is_dir():
            continue
        if entry.file_size <= 0 or entry.file_size > MAX_IMAGE_BYTES:
            raise ValueError("image ZIP member exceeds bounds")
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or path.name in by_name:
            raise ValueError("unexpected file or ambiguous image basename")
        by_name[path.name] = name
        by_stem[path.stem].append(name)
    filenames = [r["annotation_filename"] for r in records]
    if len(filenames) != len(set(filenames)):
        raise ValueError("annotation filenames are not one-to-one")
    result = {}
    for filename in filenames:
        if filename in by_name:
            result[filename] = (by_name[filename], "exact")
        else:
            choices = by_stem[PurePosixPath(filename).stem]
            if len(choices) != 1:
                raise ValueError("missing or ambiguous filename alias")
            result[filename] = (choices[0], "unique_stem_extension_alias")
    mapped = [v[0] for v in result.values()]
    if len(mapped) != len(set(mapped)) or set(mapped) != set(by_name.values()):
        raise ValueError("image archive and annotation mapping must be bijective")
    return result


def ingest(annotations: Path, images: Path, output: Path, *, workers: int = 4) -> dict:
    if workers < 1 or workers > 8:
        raise ValueError("workers must be between 1 and 8")
    if output.exists():
        raise FileExistsError("inventory output must be a new directory")
    annotation_hash, records, audit = annotation_metadata(annotations)
    image_hash = sha256(images)
    with zipfile.ZipFile(images) as archive:
        matched = match_members(archive, records)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "annotation_audit.json", audit)
        write_json(output / "environment.json", environment())
        sources = [Path(__file__), Path(__file__).with_name("images.py")]
        import vidoclens.contracts.ingestion as contracts

        sources.append(Path(contracts.__file__))
        for source in sources:
            with (output / ("source_" + source.name)).open("xb") as target:
                target.write(source.read_bytes())
        write_json(
            output / "run.json",
            {
                "started_utc": datetime.now(UTC).isoformat(),
                "annotation_archive_sha256": annotation_hash,
                "image_archive_sha256": image_hash,
                "transform": TRANSFORM,
                "workers": workers,
                "sources": {p.name: sha256(p) for p in sources},
                "image_protocol": "official_rotated_pilot_not_official_benchmark_parity",
                "external_processing": False,
                "gold_exported": False,
            },
        )
        modes, formats, splits, aliases = Counter(), Counter(), Counter(), []
        widths, heights, byte_hashes, pixel_hashes = [], [], set(), set()
        exif_transposed = 0
        inventory = output / "images.jsonl"
        with (
            inventory.open("x", encoding="utf-8", newline="\n") as stream,
            ThreadPoolExecutor(max_workers=workers) as pool,
        ):
            # Bounded batches avoid eagerly buffering the whole 4 GB archive.
            for start in range(0, len(records), workers * 2):
                batch = records[start : start + workers * 2]
                payloads = [archive.read(matched[r["annotation_filename"]][0]) for r in batch]
                # ZipFile.read verifies CRC. Full decoding and hashes happen in workers.
                for row, features in zip(batch, pool.map(fingerprints, payloads), strict=True):
                    member, method = matched[row["annotation_filename"]]
                    item = CorpusImage(
                        **row,
                        **features,
                        document_id=f"receiptvqa:{annotation_hash}:image:{row['source_image_id']}",
                        annotation_archive_sha256=annotation_hash,
                        image_archive_sha256=image_hash,
                        archive_member=member,
                        filename_match=method,
                    )
                    stream.write(item.model_dump_json() + "\n")
                    modes[item.source_mode] += 1
                    formats[item.source_format] += 1
                    splits[item.source_split] += 1
                    widths.append(item.width)
                    heights.append(item.height)
                    byte_hashes.add(item.raw_image_sha256)
                    pixel_hashes.add(item.canonical_pixel_sha256)
                    exif_transposed += item.exif_orientation not in {None, 1}
                    if method != "exact":
                        aliases.append(
                            {
                                "annotation_filename": item.annotation_filename,
                                "archive_member": member,
                            }
                        )
                if start % 1000 < workers * 2:
                    print(
                        f"images fully decoded: {min(start + len(batch), len(records))}/{len(records)}",
                        flush=True,
                    )
        summary = {
            "status": "pass",
            "finished_utc": datetime.now(UTC).isoformat(),
            "images": len(records),
            "qa_count": sum(r["qa_count"] for r in records),
            "source_splits": dict(splits),
            "raw_unique_hashes": len(byte_hashes),
            "canonical_unique_hashes": len(pixel_hashes),
            "formats": dict(formats),
            "modes": dict(modes),
            "exif_transposed": exif_transposed,
            "width_range": [min(widths), max(widths)],
            "height_range": [min(heights), max(heights)],
            "aliases": aliases,
            "image_inventory_sha256": sha256(inventory),
            "full_decode_and_crc_verified": True,
            "gold_exported": False,
            "near_duplicate_review_complete": False,
            "final_split_frozen": False,
        }
        write_json(output / "summary.json", summary)
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("annotations", "images", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    try:
        report = ingest(args.annotations, args.images, args.output, workers=args.workers)
    except Exception as error:
        # No row contents, EXIF strings or gold in console errors.
        parser.exit(
            1, f"Ingestion failed ({type(error).__name__}); incomplete output is not valid.\n"
        )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "images",
                    "qa_count",
                    "raw_unique_hashes",
                    "canonical_unique_hashes",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
