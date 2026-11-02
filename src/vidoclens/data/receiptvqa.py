"""CSV reader for an existing ReceiptVQA ZIP. No downloads or image access."""

import argparse
import csv
import hashlib
import io
import json
import re
import stat
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from vidoclens.contracts.dataset import (
    GoldReference,
    ReceiptAccessPlan,
    ReceiptAssignment,
    ReceiptQuestion,
    SupervisedReceiptExample,
)
from vidoclens.data.audit_receiptvqa import COLUMNS, MAX_BYTES, PREFIX, SPLITS


class AnnotationLoadError(ValueError):
    """Sanitized error: no CSV questions, labels or input exception context."""


@dataclass(frozen=True)
class _SourceRow:
    question: ReceiptQuestion
    answer_raw: str = field(repr=False)


def _read_split(path: Path, split: str, expected_hash: str | None = None) -> tuple[_SourceRow, ...]:
    if split not in {"train", "dev"}:
        raise PermissionError("Only train/dev are enabled; test requires a future frozen evaluator")
    try:
        if path.stat().st_size > MAX_BYTES:
            raise AnnotationLoadError("annotation archive exceeds size limit")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if expected_hash is not None and digest != expected_hash:
            raise AnnotationLoadError("access plan archive hash mismatch")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            expected = {f"{PREFIX}ReceiptVQA_{name}.csv" for name in SPLITS}
            if (
                len(names) != len(set(names))
                or not expected.issubset(names)
                or set(names) - expected - {PREFIX}
                or sum(entry.file_size for entry in entries) > MAX_BYTES
                or any(stat.S_ISLNK(entry.external_attr >> 16) for entry in entries)
                or any(entry.flag_bits & 1 for entry in entries)
            ):
                raise AnnotationLoadError("unexpected, unsafe or oversized archive members")
            # Reading this selected member verifies its CRC. Never parse test here.
            raw = archive.read(f"{PREFIX}ReceiptVQA_{split}.csv").decode("utf-8-sig")
        reader = csv.reader(io.StringIO(raw, newline=""), strict=True)
        if tuple(next(reader, ())) != COLUMNS:
            raise AnnotationLoadError("unexpected CSV header")
        rows, keys, image_files, file_images = [], set(), {}, {}
        for index, row in enumerate(reader):
            if len(row) != len(COLUMNS) or any(not item.strip() for item in row):
                raise AnnotationLoadError("malformed row or missing required cell")
            if any(re.fullmatch(r"0|[1-9][0-9]*", item) is None for item in row[:3]):
                raise AnnotationLoadError("source IDs must be canonical nonnegative integers")
            source_index, image_id, question_id = map(int, row[:3])
            if source_index != index:
                raise AnnotationLoadError("source row index is not a zero-based sequence")
            filename, question, answer = row[3:]
            key = (image_id, question_id)
            if key in keys:
                raise AnnotationLoadError("duplicate image/question identity")
            keys.add(key)
            if (image_id in image_files and image_files[image_id] != filename) or (
                filename in file_images and file_images[filename] != image_id
            ):
                raise AnnotationLoadError("image ID and filename mapping is not one-to-one")
            image_files[image_id], file_images[filename] = filename, image_id
            document_id = f"receiptvqa:{digest}:image:{image_id}"
            item = ReceiptQuestion(
                archive_sha256=digest,
                source_split=split,
                source_image_id=image_id,
                source_question_id=question_id,
                source_row_index=source_index,
                filename=filename,
                document_id=document_id,
                qid=f"{document_id}:question:{question_id}",
                question_raw=question,
                question_nfc=unicodedata.normalize("NFC", question),
            )
            rows.append(_SourceRow(question=item, answer_raw=answer))
        if not rows:
            raise AnnotationLoadError("selected split is empty")
        return tuple(rows)
    except AnnotationLoadError:
        raise
    except (OSError, UnicodeError, csv.Error, zipfile.BadZipFile, RuntimeError, ValidationError):
        raise AnnotationLoadError("archive/CSV validation failed; payload omitted") from None


def load_questions(archive: Path, *, split: str = "train") -> tuple[ReceiptQuestion, ...]:
    """Unpartitioned ingestion view, label-free. Not a teacher/training selection."""
    return tuple(row.question for row in _read_split(archive, split))


def _partition_rows(
    archive: Path, plan: ReceiptAccessPlan, split: str
) -> tuple[tuple[_SourceRow, ReceiptAssignment], ...]:
    # Revalidate at the boundary, even if a caller used Pydantic model_copy/update.
    plan = ReceiptAccessPlan.model_validate(plan.model_dump())
    rows = _read_split(archive, split, expected_hash=plan.archive_sha256)
    entries = {a.source_image_id: a for a in plan.assignments if a.source_split == split}
    images = {row.question.source_image_id for row in rows}
    if set(entries) != images:
        raise AnnotationLoadError(
            "access plan must cover exactly every receipt in the selected split"
        )
    return tuple((row, entries[row.question.source_image_id]) for row in rows)


def load_silver_questions(archive: Path, plan: ReceiptAccessPlan) -> tuple[ReceiptQuestion, ...]:
    """Only train_fit outside the explicitly selected gold groups; no label fields."""
    return tuple(
        row.question
        for row, entry in _partition_rows(archive, plan, "train")
        if entry.partition == "train_fit" and not entry.gold_for_training
    )


def _reference(row: _SourceRow) -> GoldReference:
    return GoldReference(
        qid=row.question.qid, document_id=row.question.document_id, answers=(row.answer_raw,)
    )


def load_training_examples(
    archive: Path, plan: ReceiptAccessPlan
) -> tuple[SupervisedReceiptExample, ...]:
    """Explicit gold only for selected train_fit groups; never a boolean include_gold switch."""
    return tuple(
        SupervisedReceiptExample(question=row.question, reference=_reference(row))
        for row, entry in _partition_rows(archive, plan, "train")
        if entry.partition == "train_fit" and entry.gold_for_training
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "dev"), default="train")
    args = parser.parse_args()
    try:
        records = load_questions(args.archive, split=args.split)
    except (AnnotationLoadError, PermissionError):
        parser.exit(2, "Annotation loading failed; payload omitted\n")
    print(
        json.dumps(
            {
                "split": args.split,
                "qa_rows": len(records),
                "referenced_images": len({r.document_id for r in records}),
                "archive_sha256": records[0].archive_sha256,
                "output_has_gold_fields": False,
                "images_validated": False,
            }
        )
    )


if __name__ == "__main__":
    main()
