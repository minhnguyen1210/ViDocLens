"""Image audit and provisional split records; none of these grant label access."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract, SourceID, SourceSplit

Hash64 = Annotated[str, Field(pattern=r"^[a-f0-9]{16}$")]
Hash128 = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class FeatureFingerprint(FrozenContract):
    source_image_id: SourceID
    raw_image_sha256: SHA256
    phash_rotations: tuple[Hash64, Hash64, Hash64, Hash64]
    crop60_phash: Hash64
    gradient_rotations: tuple[Hash128, Hash128, Hash128, Hash128]


class FeatureCandidate(FrozenContract):
    left_image_id: SourceID
    right_image_id: SourceID
    rotation_phash_distance: int = Field(ge=0, le=64)
    crop_phash_distance: int = Field(ge=0, le=64)
    gradient_distance: int = Field(ge=0, le=128)
    review_status: Literal["uncertain"] = "uncertain"

    @model_validator(mode="after")
    def ordered(self):
        if self.left_image_id >= self.right_image_id:
            raise ValueError("feature candidates require two ordered distinct images")
        return self


class CorpusImage(FrozenContract):
    document_id: str
    annotation_archive_sha256: SHA256
    image_archive_sha256: SHA256
    source_image_id: SourceID
    source_split: SourceSplit
    annotation_filename: str
    archive_member: str
    filename_match: Literal["exact", "unique_stem_extension_alias"]
    qa_count: int = Field(gt=0)
    raw_image_sha256: SHA256
    canonical_pixel_sha256: SHA256
    raw_bytes: int = Field(gt=0)
    raw_width: int = Field(gt=0)
    raw_height: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source_format: Literal["JPEG", "PNG"]
    source_mode: str
    exif_orientation: int | None
    canonical_mode: Literal["RGB"] = "RGB"
    canonical_file_materialized: Literal[False] = False
    transform_sha256: SHA256
    phash64: Hash64
    center_crop_phash64: Hash64
    external_processing_allowed: Literal[False] = False
    redistribution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def identity(self) -> "CorpusImage":
        expected = f"receiptvqa:{self.annotation_archive_sha256}:image:{self.source_image_id}"
        if self.document_id != expected:
            raise ValueError("document ID does not match annotation namespace")
        return self


class DuplicateGroup(FrozenContract):
    duplicate_group_id: str
    source_image_ids: tuple[SourceID, ...] = Field(min_length=1)
    source_splits: tuple[SourceSplit, ...] = Field(min_length=1)
    grouping_evidence: Literal[
        "exact_byte_or_canonical_pixel", "conservative_candidate_component"
    ] = "exact_byte_or_canonical_pixel"
    pilot_exposed: bool

    @model_validator(mode="after")
    def unique_members(self) -> "DuplicateGroup":
        if tuple(sorted(set(self.source_image_ids))) != self.source_image_ids:
            raise ValueError("group members must be sorted and unique")
        if len(set(self.source_splits)) != len(self.source_splits):
            raise ValueError("group source splits must be unique")
        return self


class NearDuplicateCandidate(FrozenContract):
    left_image_id: SourceID
    right_image_id: SourceID
    left_group_id: str
    right_group_id: str
    full_phash_distance: int = Field(ge=0, le=64)
    crop_phash_distance: int = Field(ge=0, le=64)
    crosses_official_splits: bool
    review_status: Literal["pending"] = "pending"
    auto_merge_allowed: Literal[False] = False

    @model_validator(mode="after")
    def ordered_pair(self) -> "NearDuplicateCandidate":
        if self.left_image_id >= self.right_image_id or self.left_group_id == self.right_group_id:
            raise ValueError("candidate must be an ordered pair of distinct exact groups")
        return self


class DraftAssignment(FrozenContract):
    source_image_id: SourceID
    source_split: SourceSplit
    duplicate_group_id: str
    partition: Literal[
        "train_fit", "audit_holdout", "dev_select", "dev_calibrate", "test", "quarantine"
    ]
    quarantine_reason: Literal["train_overlaps_dev_or_test", "dev_overlaps_test"] | None = None
    pilot_exposed: bool

    @model_validator(mode="after")
    def boundaries(self) -> "DraftAssignment":
        allowed = {
            "train": {"train_fit", "audit_holdout", "quarantine"},
            "dev": {"dev_select", "dev_calibrate", "quarantine"},
            "test": {"test"},
        }
        if self.partition not in allowed[self.source_split]:
            raise ValueError("draft partition changes official split role")
        if (self.partition == "quarantine") != (self.quarantine_reason is not None):
            raise ValueError(
                "quarantine requires an explicit reason and no other partition may have one"
            )
        if self.pilot_exposed and self.partition == "audit_holdout":
            raise ValueError("pilot exposure cannot enter audit holdout")
        if self.quarantine_reason is not None:
            expected = {"train": "train_overlaps_dev_or_test", "dev": "dev_overlaps_test"}
            if expected.get(self.source_split) != self.quarantine_reason:
                raise ValueError("quarantine reason does not match source split")
        return self


class SplitDraft(FrozenContract):
    status: Literal["draft"] = "draft"
    training_allowed: Literal[False] = False
    near_duplicate_review_complete: Literal[False] = False
    annotation_archive_sha256: SHA256
    image_inventory_sha256: SHA256
    seed: int = 42
    assignments: tuple[DraftAssignment, ...] = Field(min_length=1)
    gold_group_sets: dict[str, tuple[str, ...]]

    @model_validator(mode="after")
    def group_integrity(self) -> "SplitDraft":
        ids, policies, training = set(), {}, set()
        for row in self.assignments:
            if row.source_image_id in ids:
                raise ValueError("duplicate image assignment")
            ids.add(row.source_image_id)
            if row.partition == "quarantine":
                continue
            prior = policies.setdefault(row.duplicate_group_id, row.partition)
            if prior != row.partition:
                raise ValueError("non-quarantined group crosses draft partitions")
            if row.partition == "train_fit":
                training.add(row.duplicate_group_id)
        if set(self.gold_group_sets) != {"5", "10", "25", "100"}:
            raise ValueError("four nested gold budgets are required")
        previous = set()
        for k in ("5", "10", "25", "100"):
            selected = self.gold_group_sets[k]
            current = set(selected)
            if len(current) != len(selected) or not previous <= current <= training:
                raise ValueError("gold IDs must be unique nested subsets of train_fit groups")
            previous = current
        if previous != training:
            raise ValueError("G100 must cover all train_fit groups")
        return self
