import csv
import hashlib
import io
import json
import subprocess
import sys
import traceback
import unicodedata
import zipfile

import pytest
from pydantic import ValidationError

from vidoclens.contracts.dataset import ReceiptAccessPlan, ReceiptAssignment, ReceiptQuestion
from vidoclens.data.audit_receiptvqa import COLUMNS, PREFIX
from vidoclens.data.receiptvqa import (
    AnnotationLoadError,
    load_questions,
    load_silver_questions,
    load_training_examples,
)
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold


@pytest.fixture
def source_rows():
    return {
        "train": [
            ["0", "1", "7", "one.jpg", "Tên cửa hàng?", "GOLD_ONLY_1"],
            ["1", "1", "8", "one.jpg", "Các món?", "  GOLD_ONLY_A\r\nGOLD_ONLY_B  "],
            ["2", "2", "7", "two.jpg", "Địa chỉ?", "GOLD_ONLY_2"],
            ["3", "3", "7", "three.jpg", "Tổng tiền?", "GOLD_ONLY_AUDIT"],
        ],
        "dev": [
            ["0", "4", "7", "four.jpg", "Tổng tiền?", "GOLD_ONLY_DEV_SELECT"],
            ["1", "5", "7", "five.jpg", "Tổng tiền?", "GOLD_ONLY_DEV_CALIBRATE"],
        ],
        "test": [["0", "6", "7", "six.jpg", "Tổng tiền?", "GOLD_ONLY_TEST"]],
    }


def archive_at(tmp_path, rows, *, extra=None, header=COLUMNS, bom=False):
    path = tmp_path / "ReceiptVQA_annotations.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for split, content_rows in rows.items():
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(content_rows)
            content = stream.getvalue().encode("utf-8-sig" if bom else "utf-8")
            archive.writestr(f"{PREFIX}ReceiptVQA_{split}.csv", content)
        if extra:
            archive.writestr(extra, "GOLD_ONLY_EXTRA")
    return path


def plan_for(path):
    return ReceiptAccessPlan(
        archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        grouping_status="receipt_only",
        assignments=tuple(
            ReceiptAssignment(
                source_image_id=image,
                source_split=split,
                partition=partition,
                duplicate_group_id=f"receipt-{image}",
                gold_for_training=selected,
            )
            for image, split, partition, selected in (
                (1, "train", "train_fit", True),
                (2, "train", "train_fit", False),
                (3, "train", "audit_holdout", False),
                (4, "dev", "dev_select", False),
                (5, "dev", "dev_calibrate", False),
                (6, "test", "test", False),
            )
        ),
    )


def test_default_view_contains_no_gold_fields_or_content(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    before = path.read_bytes()
    records = load_questions(path)
    assert len(records) == 4
    forbidden = {"answer", "answers", "answer_parts", "label", "reference", "gold"}
    for record in records:
        payload = record.model_dump()
        assert not forbidden.intersection(payload)
        assert "GOLD_ONLY" not in record.model_dump_json() + repr(record)
        with pytest.raises(ValidationError):
            ReceiptQuestion.model_validate({**payload, "answers": ["GOLD_ONLY_POISON"]})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_ids_are_namespaced_and_question_id_is_not_globally_unique(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    first = load_questions(path)
    assert first == load_questions(path)
    assert len({r.qid for r in first}) == 4
    assert first[0].document_id == first[1].document_id
    assert first[0].qid != first[2].qid
    source_rows["dev"][0][-1] = "GOLD_ONLY_NEW_VERSION"
    archive_at(tmp_path, source_rows)
    second = load_questions(path)
    assert first[0].qid != second[0].qid


def test_raw_question_and_gold_newlines_are_preserved(tmp_path, source_rows):
    original_question = unicodedata.normalize("NFD", "  Tên cửa hàng?  ")
    source_rows["train"][0][4] = original_question
    path = archive_at(tmp_path, source_rows, bom=True)
    questions = load_questions(path)
    assert questions[0].question_raw == original_question
    assert questions[0].question_nfc == "  Tên cửa hàng?  "
    examples = load_training_examples(path, plan_for(path))
    assert examples[1].reference.answers == ("  GOLD_ONLY_A\r\nGOLD_ONLY_B  ",)
    assert "GOLD_ONLY" not in repr(examples[1])


def test_gold_and_silver_are_selected_by_whole_receipt(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    plan = plan_for(path)
    gold = load_training_examples(path, plan)
    silver = load_silver_questions(path, plan)
    assert len(gold) == 2  # Both questions from receipt 1 belong together.
    assert {x.question.source_image_id for x in gold} == {1}
    assert {x.source_image_id for x in silver} == {2}
    assert "GOLD_ONLY" not in json.dumps([x.model_dump() for x in silver])
    assert {x.question.qid for x in gold}.isdisjoint(x.qid for x in silver)
    for partition, expected in (
        ("audit_holdout", "GOLD_ONLY_AUDIT"),
        ("dev_select", "GOLD_ONLY_DEV_SELECT"),
        ("dev_calibrate", "GOLD_ONLY_DEV_CALIBRATE"),
    ):
        references = load_evaluation_gold(path, plan, partition=partition)
        assert len(references) == 1
        assert references[0].answers == (expected,)


@pytest.mark.parametrize(
    "split,partition", [("train", "audit_holdout"), ("dev", "dev_select"), ("test", "test")]
)
def test_heldout_training_gold_grant_is_rejected(split, partition):
    with pytest.raises(ValidationError, match="only train_fit"):
        ReceiptAssignment(
            source_image_id=1,
            source_split=split,
            partition=partition,
            duplicate_group_id="g",
            gold_for_training=True,
        )


def test_source_split_cannot_be_relabelled_as_training():
    with pytest.raises(ValidationError, match="incompatible"):
        ReceiptAssignment(
            source_image_id=1, source_split="test", partition="train_fit", duplicate_group_id="g"
        )


@pytest.mark.parametrize("change", ["partition", "gold"])
def test_duplicate_group_cannot_cross_policy(tmp_path, source_rows, change):
    path = archive_at(tmp_path, source_rows)
    payload = plan_for(path).model_dump()
    payload["assignments"][1]["duplicate_group_id"] = "receipt-1"
    if change == "partition":
        payload["assignments"][1]["partition"] = "audit_holdout"
    with pytest.raises(ValidationError, match="duplicate group"):
        ReceiptAccessPlan.model_validate(payload)


@pytest.mark.parametrize("change", ["hash", "partial", "unknown"])
def test_bad_access_plan_does_not_expose_labels(tmp_path, source_rows, change):
    path = archive_at(tmp_path, source_rows)
    payload = plan_for(path).model_dump()
    if change == "hash":
        payload["archive_sha256"] = "0" * 64
    elif change == "partial":
        payload["assignments"] = payload["assignments"][1:]
    else:
        payload["assignments"][0]["source_image_id"] = 99
    plan = ReceiptAccessPlan.model_validate(payload)
    with pytest.raises(AnnotationLoadError):
        load_training_examples(path, plan)


def test_model_copy_does_not_bypass_plan_validation(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    plan = plan_for(path)
    changed = plan.assignments[2].model_copy(update={"gold_for_training": True})
    plan = plan.model_copy(update={"assignments": (changed, *plan.assignments[:2])})
    with pytest.raises(ValidationError):
        load_training_examples(path, plan)


def test_test_access_is_blocked_before_any_archive_read(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    plan = plan_for(path)
    missing = tmp_path / "does-not-exist.zip"
    with pytest.raises(PermissionError):
        load_questions(missing, split="test")
    for partition in ("test", "ood", "train_fit"):
        with pytest.raises(PermissionError):
            load_evaluation_gold(missing, plan, partition=partition)


def test_selected_loader_never_opens_test_member(tmp_path, source_rows, monkeypatch):
    path = archive_at(tmp_path, source_rows)
    original = zipfile.ZipFile.read

    def guarded_read(self, name, *args, **kwargs):
        assert "test.csv" not in name
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", guarded_read)
    assert len(load_questions(path, split="train")) == 4
    assert len(load_questions(path, split="dev")) == 2


@pytest.mark.parametrize("defect", ["duplicate", "mapping", "missing", "extra", "index", "path"])
def test_invalid_csv_is_rejected_before_returning_any_records(tmp_path, source_rows, defect):
    rows = source_rows["train"]
    if defect == "duplicate":
        rows[1][2] = rows[0][2]
    elif defect == "mapping":
        rows[1][3] = "conflict.jpg"
    elif defect == "missing":
        rows[0][-1] = " "
    elif defect == "extra":
        rows[0].append("GOLD_ONLY_EXTRA")
    elif defect == "index":
        rows[0][0] = "99"
    elif defect == "path":
        rows[0][3] = "../GOLD_ONLY_UNSAFE.jpg"
    path = archive_at(tmp_path, source_rows)
    with pytest.raises(AnnotationLoadError) as error:
        load_questions(path)
    assert "GOLD_ONLY" not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("defect", ["header", "member", "corrupt"])
def test_archive_schema_and_integrity_checks(tmp_path, source_rows, defect):
    path = archive_at(
        tmp_path,
        source_rows,
        extra="../escape.csv" if defect == "member" else None,
        header=tuple(reversed(COLUMNS)) if defect == "header" else COLUMNS,
    )
    if defect == "corrupt":
        path.write_bytes(b"GOLD_ONLY_NOT_A_ZIP")
    with pytest.raises(AnnotationLoadError):
        load_questions(path)


def test_cli_only_prints_aggregate_metadata(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    result = subprocess.run(
        [sys.executable, "-m", "vidoclens.data.receiptvqa", "--archive", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "GOLD_ONLY" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["qa_rows"] == 4


def test_crc_failure_is_not_silently_loaded(tmp_path, source_rows):
    path = archive_at(tmp_path, source_rows)
    raw = path.read_bytes()
    assert b"GOLD_ONLY_1" in raw
    path.write_bytes(raw.replace(b"GOLD_ONLY_1", b"GOLD_ONLY_X", 1))
    with pytest.raises(AnnotationLoadError):
        load_questions(path)


def test_annotation_size_limit_is_checked_before_read(tmp_path, source_rows, monkeypatch):
    path = archive_at(tmp_path, source_rows)
    monkeypatch.setattr("vidoclens.data.receiptvqa.MAX_BYTES", 1)
    with pytest.raises(AnnotationLoadError, match="size limit"):
        load_questions(path)
