import csv
import io
import json
import subprocess
import sys
import zipfile

import pytest

from vidoclens.data.audit_receiptvqa import COLUMNS, PREFIX, SPLITS, audit_archive


def make_archive(tmp_path, transform=None, extra=None):
    target = tmp_path / "annotations.zip"
    with zipfile.ZipFile(target, "w") as archive:
        for number, split in enumerate(SPLITS, 1):
            rows = [["0", str(number), "1", f"{number}.jpg", "PRIVATE_QUESTION", "PRIVATE\nANSWER"]]
            if transform:
                transform(split, rows)
            content = io.StringIO(newline="")
            writer = csv.writer(content)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
            archive.writestr(f"{PREFIX}ReceiptVQA_{split}.csv", content.getvalue())
        if extra:
            archive.writestr(extra, "not extracted")
    return target


def test_audit_keeps_gold_out_of_report_and_preserves_input(tmp_path):
    path = make_archive(tmp_path)
    original = path.read_bytes()
    report = audit_archive(path)
    assert report["status"] == "pass"
    assert report["total_qa_rows"] == report["union_image_ids"] == 3
    assert report["splits"]["train"]["train_only_text_structure"]["answers_with_newline"] == 1
    for split in ("dev", "test"):
        assert "train_only_text_structure" not in report["splits"][split]
    assert "PRIVATE" not in json.dumps(report)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_reused_question_id_for_different_images_is_valid(tmp_path):
    def transform(split, rows):
        if split == "train":
            rows.append(["1", "99", "1", "99.jpg", "Q", "A"])

    report = audit_archive(make_archive(tmp_path, transform))
    assert report["status"] == "pass"
    assert report["splits"]["train"]["unique_question_ids"] == 1


@pytest.mark.parametrize("violation", ["duplicate", "overlap", "missing", "malformed", "mapping"])
def test_data_integrity_violations_fail(tmp_path, violation):
    def transform(split, rows):
        if split != "train":
            return
        if violation == "duplicate":
            rows.append(["1", *rows[0][1:]])
        elif violation == "overlap":
            rows[0][1], rows[0][3] = "2", "2.jpg"
        elif violation == "missing":
            rows[0][-1] = " "
        elif violation == "malformed":
            rows[0].pop()
        elif violation == "mapping":
            rows.append(["1", "1", "2", "other.jpg", "Q", "A"])

    report = audit_archive(make_archive(tmp_path, transform))
    assert report["status"] == "fail"
    assert report["failures"]


@pytest.mark.parametrize("member", ["../escape.csv", "/absolute.csv", "unexpected.csv"])
def test_unexpected_zip_members_rejected_without_extraction(tmp_path, member):
    path = make_archive(tmp_path, extra=member)
    with pytest.raises(ValueError, match="ZIP members"):
        audit_archive(path)
    assert list(tmp_path.iterdir()) == [path]


def test_cli_persists_report_and_refuses_overwrite(tmp_path):
    path = make_archive(tmp_path)
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        "-m",
        "vidoclens.data.audit_receiptvqa",
        "--archive",
        str(path),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "PRIVATE" not in first.stdout + first.stderr
    original = output.read_bytes()
    assert json.loads(original)["status"] == "pass"
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode == 2
    assert output.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 2
