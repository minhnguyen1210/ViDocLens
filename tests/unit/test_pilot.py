import hashlib
import json

import pytest
from pydantic import ValidationError

from vidoclens.common.pilot import load_pilot, percentile, write_json
from vidoclens.contracts.pilot import Phase0PilotManifest


@pytest.fixture
def pilot_files(tmp_path):
    image = tmp_path / "fixture.bin"
    image.write_bytes(b"synthetic non-image for input boundary tests only")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    row = {
        "document_id": "synthetic-image-1",
        "qid": "synthetic-q1",
        "question_raw": "Total?",
        "image_path": image.name,
        "image_sha256": digest,
        "width": 1,
        "height": 1,
        "mode": "RGB",
        "duplicate_group_image_ids": [1],
        "exclude_from_future_audit_holdout": True,
    }
    manifest = tmp_path / "pilot.json"
    inventory = tmp_path / "images.json"
    manifest.write_text(json.dumps({"selection": "synthetic", "pilot": [row]}))
    inventory.write_text(json.dumps([{"image_sha256": digest, "source_split": "train"}]))
    return tmp_path, manifest, inventory, row


def test_train_only_pilot_is_label_free(pilot_files):
    root, manifest, inventory, _ = pilot_files
    result = load_pilot(root, manifest, inventory)
    assert len(result.pilot) == 1
    assert "answer" not in result.pilot[0].model_dump()


@pytest.mark.parametrize("gold_field", ["answer", "answers", "gold", "reference"])
def test_pilot_rejects_gold_fields(pilot_files, gold_field):
    _, _, _, row = pilot_files
    with pytest.raises(ValidationError):
        Phase0PilotManifest(selection="synthetic", pilot=[{**row, gold_field: "secret-label"}])


@pytest.mark.parametrize("split", ["dev", "test", "ood", "unknown"])
def test_cross_split_hash_is_blocked_even_with_train_copy(pilot_files, split):
    root, manifest, inventory, row = pilot_files
    inventory.write_text(
        json.dumps(
            [
                {"image_sha256": row["image_sha256"], "source_split": "train"},
                {"image_sha256": row["image_sha256"], "source_split": split},
            ]
        )
    )
    with pytest.raises(ValueError, match="exclusively"):
        load_pilot(root, manifest, inventory)


def test_changed_image_is_blocked(pilot_files):
    root, manifest, inventory, row = pilot_files
    (root / row["image_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_pilot(root, manifest, inventory)


def test_path_escape_is_blocked_before_reading(pilot_files):
    root, manifest, inventory, row = pilot_files
    row["image_path"] = "../outside.bin"
    manifest.write_text(json.dumps({"selection": "synthetic", "pilot": [row]}))
    with pytest.raises(ValueError, match="escapes"):
        load_pilot(root, manifest, inventory)


def test_missing_train_membership_is_blocked(pilot_files):
    root, manifest, inventory, _ = pilot_files
    inventory.write_text("[]")
    with pytest.raises(ValueError, match="exclusively"):
        load_pilot(root, manifest, inventory)


def test_duplicate_receipt_cannot_inflate_pilot(pilot_files):
    *_, row = pilot_files
    with pytest.raises(ValidationError, match="duplicate"):
        Phase0PilotManifest(selection="synthetic", pilot=[row, row])


def test_pilot_cannot_reenter_future_holdout(pilot_files):
    *_, row = pilot_files
    with pytest.raises(ValidationError):
        Phase0PilotManifest(
            selection="synthetic", pilot=[{**row, "exclude_from_future_audit_holdout": False}]
        )


def test_evidence_output_cannot_be_overwritten(tmp_path):
    path = tmp_path / "evidence.json"
    write_json(path, {"status": "fail"})
    with pytest.raises(FileExistsError):
        write_json(path, {"status": "pass"})
    assert json.loads(path.read_text()) == {"status": "fail"}


def test_latency_percentile_interpolates():
    assert percentile([10, 2, 6], 0.5) == 6
    assert percentile([2, 10], 0.95) == pytest.approx(9.6)
