"""Read-only annotation audit. Never emit questions, answers or per-receipt IDs."""

import argparse
import csv
import hashlib
import io
import json
import stat
import tempfile
import unicodedata
import zipfile
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

SPLITS = ("train", "dev", "test")
COLUMNS = ("", "image_id", "question_id", "filename", "question", "answer")
PREFIX = "ReceiptVQA_annotations/"
MAX_BYTES = 64 * 1024 * 1024


def audit_archive(path: Path) -> dict:
    """Validate the official CSV layout without extracting or changing the archive.

    Test/dev text is read only for CSV parsing and missing-value checks. This is
    an archive audit, not a training loader, image audit or official evaluator.
    Raised errors deliberately omit potentially sensitive archive/row contents.
    """
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Archive exceeds the annotation audit size limit")
    archive_bytes = path.read_bytes()
    report = {
        "audit_version": "1.1",
        "checked_at": datetime.now(UTC).isoformat(),
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "archive_bytes": len(archive_bytes),
        "splits": {},
        "failures": [],
        "image_bytes_available": False,
        "image_dedup_performed": False,
        "extracted_to_filesystem": False,
    }
    members = {split: f"{PREFIX}ReceiptVQA_{split}.csv" for split in SPLITS}
    ids_by_split, files_by_split = {}, {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        expected = set(members.values())
        if (
            len(entries) > 4
            or len(names) != len(set(names))
            or not expected.issubset(names)
            or set(names) - expected - {PREFIX}
            or sum(entry.file_size for entry in entries) > MAX_BYTES
            or any(stat.S_ISLNK(entry.external_attr >> 16) for entry in entries)
            or any(entry.flag_bits & 1 for entry in entries)
        ):
            raise ValueError("Unexpected, duplicated, unsafe or oversized ZIP members")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        report["crc_valid"] = True
        report["uncompressed_bytes"] = sum(entry.file_size for entry in entries)
        for split, member in members.items():
            payload = archive.read(member)
            try:
                reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
                if tuple(next(reader, ())) != COLUMNS:
                    raise ValueError("Unexpected CSV header")
                image_files, file_images, keys, question_ids = {}, {}, set(), set()
                counts = {
                    "qa_rows": 0,
                    "malformed_rows": 0,
                    "missing_cells": 0,
                    "invalid_integer_ids": 0,
                    "nonsequential_index": 0,
                    "duplicate_image_question_keys": 0,
                    "image_filename_conflicts": 0,
                }
                text_structure = {
                    "answers_with_newline": 0,
                    "answers_with_sep_delimiter": 0,
                    "questions_not_NFC": 0,
                    "answers_not_NFC": 0,
                }
                for index, row in enumerate(reader):
                    counts["qa_rows"] += 1
                    if len(row) != len(COLUMNS):
                        counts["malformed_rows"] += 1
                        continue
                    counts["missing_cells"] += sum(not value.strip() for value in row)
                    idx, image_id, question_id, filename, question, answer = row
                    try:
                        source_index, image_id, question_id = map(int, (idx, image_id, question_id))
                        if min(source_index, image_id, question_id) < 0:
                            raise ValueError
                    except ValueError:
                        counts["invalid_integer_ids"] += 1
                        continue
                    counts["nonsequential_index"] += source_index != index
                    key = (image_id, question_id)
                    counts["duplicate_image_question_keys"] += key in keys
                    keys.add(key)
                    question_ids.add(question_id)
                    counts["image_filename_conflicts"] += (
                        image_id in image_files and image_files[image_id] != filename
                    ) or (filename in file_images and file_images[filename] != image_id)
                    image_files[image_id] = filename
                    file_images[filename] = image_id
                    if split == "train":
                        text_structure["answers_with_newline"] += "\n" in answer or "\r" in answer
                        text_structure["answers_with_sep_delimiter"] += "¡sep¿" in answer
                        text_structure["questions_not_NFC"] += not unicodedata.is_normalized(
                            "NFC", question
                        )
                        text_structure["answers_not_NFC"] += not unicodedata.is_normalized(
                            "NFC", answer
                        )
            except (UnicodeError, csv.Error) as exc:
                raise ValueError("CSV cannot be decoded or parsed") from exc
            report["failures"].extend(
                f"{split}:{name}" for name, value in counts.items() if name != "qa_rows" and value
            )
            if not counts["qa_rows"]:
                report["failures"].append(f"{split}:empty_split")
            report["splits"][split] = {
                **counts,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "utf8_bom": payload.startswith(b"\xef\xbb\xbf"),
                "unique_image_ids": len(image_files),
                "unique_filenames": len(file_images),
                "unique_question_ids": len(question_ids),
            }
            if split == "train":
                report["splits"][split]["train_only_text_structure"] = text_structure
            ids_by_split[split], files_by_split[split] = set(image_files), set(file_images)
    report["cross_split_identifier_overlap"] = {}
    for left, right in combinations(SPLITS, 2):
        name = f"{left}__{right}"
        overlap = {
            "image_id": len(ids_by_split[left] & ids_by_split[right]),
            "filename": len(files_by_split[left] & files_by_split[right]),
        }
        report["cross_split_identifier_overlap"][name] = overlap
        if any(overlap.values()):
            report["failures"].append(f"{name}:identifier_overlap")
    report["total_qa_rows"] = sum(item["qa_rows"] for item in report["splits"].values())
    report["union_image_ids"] = len(set.union(*ids_by_split.values()))
    report["union_filenames"] = len(set.union(*files_by_split.values()))
    report["status"] = "pass" if not report["failures"] else "fail"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.archive.resolve() == args.output.resolve() or args.output.exists():
        parser.error("Output must be a new file, separate from the input archive")
    try:
        report = audit_archive(args.archive)
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as exc:
        # Do not dump exception details that may contain local paths or dataset text.
        parser.exit(2, f"Annotation audit could not complete ({type(exc).__name__})\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=args.output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if args.output.exists():
            parser.error("Output appeared during audit; refusing to overwrite")
        temporary.rename(args.output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(
        json.dumps(
            {
                "status": report["status"],
                "qa_rows": report["total_qa_rows"],
                "referenced_images": report["union_image_ids"],
            }
        )
    )
    raise SystemExit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
