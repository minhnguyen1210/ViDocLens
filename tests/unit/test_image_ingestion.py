import csv
import hashlib
import io
import json
import stat
import zipfile

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from vidoclens.contracts.dataset import ReceiptAccessPlan
from vidoclens.contracts.ingestion import CorpusImage, SplitDraft
from vidoclens.data.audit_receiptvqa import COLUMNS, PREFIX
from vidoclens.data.dedup import exact_groups, near_candidates
from vidoclens.data.images import canonical_image, fingerprints, pixel_sha256
from vidoclens.data.ingest_receiptvqa import annotation_metadata, ingest, match_members
from vidoclens.data.split_draft import build, draft_split


def encoded(color="white", size=(12, 8), **kwargs):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG", **kwargs)
    return stream.getvalue()


def record(index, split="train", raw=None, pixel=None, phash=None):
    digest = hashlib.sha256(str(index).encode()).hexdigest()
    return CorpusImage(
        document_id=f"receiptvqa:{'a' * 64}:image:{index}",
        annotation_archive_sha256="a" * 64,
        image_archive_sha256="b" * 64,
        source_image_id=index,
        source_split=split,
        annotation_filename=f"{index}.png",
        archive_member=f"images/{index}.png",
        filename_match="exact",
        qa_count=2,
        raw_image_sha256=raw or digest,
        canonical_pixel_sha256=pixel or digest,
        raw_bytes=100,
        raw_width=12,
        raw_height=8,
        width=12,
        height=8,
        source_format="PNG",
        source_mode="RGB",
        exif_orientation=None,
        transform_sha256="c" * 64,
        phash64=phash or f"{index:016x}",
        center_crop_phash64=phash or f"{index:016x}",
    )


def test_pixel_hash_deduplicates_distinct_lossless_encodings():
    left = encoded(compress_level=0)
    right = encoded(compress_level=9)
    assert left != right
    a, _ = canonical_image(left)
    b, _ = canonical_image(right)
    assert pixel_sha256(a) == pixel_sha256(b)


def test_pixel_hash_binds_dimensions_not_only_rgb_bytes():
    assert pixel_sha256(Image.new("RGB", (12, 8))) != pixel_sha256(Image.new("RGB", (8, 12)))


def test_exif_rotation_applied_and_metadata_removed():
    exif = Image.Exif()
    exif[274] = 6
    data = encoded(size=(12, 8), exif=exif)
    image, info = canonical_image(data)
    assert image.size == (8, 12) and info["exif_orientation"] == 6
    assert image.mode == "RGB" and not image.info and not image.getexif()


@pytest.mark.parametrize("payload", [b"", b"not an image"])
def test_corrupt_image_fails_full_decode(payload):
    with pytest.raises((ValueError, OSError)):
        canonical_image(payload)


@pytest.mark.parametrize(
    "name", ["../escape.jpg", "/absolute.jpg", "images\\escape.jpg", "C:escape.jpg"]
)
def test_unsafe_zip_paths_rejected(name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        # Windows ZipFile normalizes backslashes when writing; patch both ZIP
        # filename headers so the test exercises an actual untrusted backslash.
        z.writestr(name.replace("\\", "/"), encoded())
    if "\\" in name:
        stream = io.BytesIO(
            stream.getvalue().replace(name.replace("\\", "/").encode(), name.encode())
        )
    with zipfile.ZipFile(stream) as z, pytest.raises(ValueError, match="unsafe"):
        match_members(z, [])


def test_symlink_zip_rejected():
    stream = io.BytesIO()
    entry = zipfile.ZipInfo("images/one.png")
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(entry, b"target")
    with zipfile.ZipFile(stream) as z, pytest.raises(ValueError, match="symlink"):
        match_members(z, [])


def test_unique_stem_alias_is_explicit():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("images/one.jpg", encoded())
    with zipfile.ZipFile(stream) as z:
        assert match_members(z, [{"annotation_filename": "one.png"}]) == {
            "one.png": ("images/one.jpg", "unique_stem_extension_alias")
        }


def test_ambiguous_stem_is_not_guessed():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("images/one.jpg", encoded())
        z.writestr("images/one.jpeg", encoded())
    with zipfile.ZipFile(stream) as z, pytest.raises(ValueError, match="ambiguous"):
        match_members(z, [{"annotation_filename": "one.png"}])


def test_extra_archive_image_fails_bijection():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("images/extra.png", encoded())
    with zipfile.ZipFile(stream) as z, pytest.raises(ValueError, match="bijective"):
        match_members(z, [])


def test_transitive_exact_groups_and_pilot_exposure():
    images = [
        record(1, raw="d" * 64),
        record(2, raw="d" * 64, pixel="e" * 64),
        record(3, split="dev", pixel="e" * 64),
    ]
    groups = exact_groups(images, {1})
    assert len(groups) == 1 and groups[0].source_image_ids == (1, 2, 3)
    assert groups[0].pilot_exposed and set(groups[0].source_splits) == {"train", "dev"}
    assert groups == exact_groups(list(reversed(images)), {1})


def test_draft_quarantines_train_dev_test_overlap_and_preserves_test():
    images = [
        record(1, raw="d" * 64),
        record(2, "dev", raw="d" * 64),
        record(3, "test", raw="d" * 64),
    ]
    draft = draft_split(images, exact_groups(images, set()), "f" * 64)
    assert [a.partition for a in draft.assignments] == ["quarantine", "quarantine", "test"]
    assert not draft.training_allowed
    with pytest.raises(ValidationError):
        ReceiptAccessPlan.model_validate(draft.model_dump())


def test_draft_groups_are_disjoint_nested_reproducible_and_pilot_safe():
    images = (
        [record(i) for i in range(1, 101)]
        + [record(i, "dev") for i in range(101, 111)]
        + [record(111, "test")]
    )
    groups = exact_groups(images, {1, 2, 3})
    a = draft_split(images, groups, "f" * 64)
    b = draft_split(list(reversed(images)), groups, "f" * 64)
    assert a == b
    assert sum(r.partition == "audit_holdout" for r in a.assignments) == 10
    assert sum(r.partition == "dev_calibrate" for r in a.assignments) == 3
    assert not any(r.pilot_exposed and r.partition == "audit_holdout" for r in a.assignments)
    assert (
        set(a.gold_group_sets["5"])
        <= set(a.gold_group_sets["10"])
        <= set(a.gold_group_sets["25"])
        <= set(a.gold_group_sets["100"])
    )
    poisoned = a.model_dump()
    poisoned["training_allowed"] = True
    with pytest.raises(ValidationError):
        SplitDraft.model_validate(poisoned)


def test_similar_fingerprint_never_auto_merges():
    pytest.importorskip("numpy")
    images = [record(1, phash="8" * 16), record(2, "test", phash="8" * 16)]
    groups = exact_groups(images, set())
    queue = list(near_candidates(images, groups))
    assert len(groups) == 2 and len(queue) == 1 and queue[0].crosses_official_splits
    assert not queue[0].auto_merge_allowed and queue[0].review_status == "pending"


def test_perceptual_fingerprint_finds_reencoding_despite_pixel_difference():
    pytest.importorskip("numpy")
    picture = Image.new("RGB", (160, 240), "white")
    draw = ImageDraw.Draw(picture)
    for y, width in [(10, 120), (40, 50), (90, 100), (130, 70), (170, 120)]:
        draw.rectangle((12, y, width, y + 8), fill="black")
    png, jpeg = io.BytesIO(), io.BytesIO()
    picture.save(png, format="PNG")
    picture.save(jpeg, format="JPEG", quality=90)
    left, right = fingerprints(png.getvalue()), fingerprints(jpeg.getvalue())
    assert left["canonical_pixel_sha256"] != right["canonical_pixel_sha256"]
    assert (int(left["phash64"], 16) ^ int(right["phash64"], 16)).bit_count() <= 6


@pytest.mark.parametrize("full,crop,expected", [(6, 64, True), (7, 5, False), (64, 4, True)])
def test_near_candidate_threshold_boundaries(full, crop, expected):
    pytest.importorskip("numpy")
    left = record(1, phash="0" * 16)
    right = record(2).model_copy(
        update={
            "phash64": f"{(1 << full) - 1:016x}",
            "center_crop_phash64": f"{(1 << crop) - 1:016x}",
        }
    )
    images = [left, right]
    assert bool(list(near_candidates(images, exact_groups(images, set())))) is expected


def test_inventory_corruption_is_blocked_before_draft_output(tmp_path):
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    (inventory / "images.jsonl").write_text("changed bytes")
    (inventory / "summary.json").write_text(
        json.dumps({"status": "pass", "image_inventory_sha256": "a" * 64})
    )
    output = tmp_path / "draft"
    with pytest.raises(ValueError, match="checksum"):
        build(inventory, tmp_path / "not-read-pilot.json", output)
    assert not output.exists()


def test_draft_rejects_gold_group_outside_training():
    images = [record(1), record(2, "test")]
    draft = draft_split(images, exact_groups(images, set()), "f" * 64)
    poisoned = draft.model_dump()
    test_group = next(a.duplicate_group_id for a in draft.assignments if a.partition == "test")
    poisoned["gold_group_sets"]["5"] = [test_group]
    with pytest.raises(ValidationError, match="subsets"):
        SplitDraft.model_validate(poisoned)


def test_false_group_split_metadata_is_rejected():
    images = [record(1)]
    groups = exact_groups(images, set())
    bad = groups[0].model_copy(update={"source_splits": ("dev",)})
    with pytest.raises(ValueError, match="inconsistent"):
        draft_split(images, (bad,), "f" * 64)


def test_end_to_end_ingestion_is_label_free_and_cannot_overwrite(tmp_path):
    pytest.importorskip("numpy")
    annotations = tmp_path / "annotations.zip"
    images = tmp_path / "images.zip"
    with zipfile.ZipFile(annotations, "w") as z:
        for index, split in enumerate(("train", "dev", "test"), 1):
            text = io.StringIO(newline="")
            w = csv.writer(text)
            w.writerow(COLUMNS)
            w.writerow([0, index, 0, f"{index}.png", "QUESTION_SENTINEL", "GOLD_SENTINEL"])
            z.writestr(f"{PREFIX}ReceiptVQA_{split}.csv", text.getvalue())
    with zipfile.ZipFile(images, "w") as z:
        for i in range(1, 4):
            z.writestr(f"images/{i}.png", encoded())
    before = hashlib.sha256(images.read_bytes()).hexdigest()
    _, meta, _ = annotation_metadata(annotations)
    assert "SENTINEL" not in json.dumps(meta)
    out = tmp_path / "new-run"
    report = ingest(annotations, images, out, workers=1)
    assert report["images"] == 3 and report["canonical_unique_hashes"] == 1
    assert "SENTINEL" not in (out / "images.jsonl").read_text()
    assert hashlib.sha256(images.read_bytes()).hexdigest() == before
    with pytest.raises(FileExistsError):
        ingest(annotations, images, out)
