"""Annotation-only contracts: no invented image hashes, geometry or access grants."""

import unicodedata
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from vidoclens.contracts.models import Contract

SHA256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SourceID = Annotated[int, Field(strict=True, ge=0)]
SourceSplit = Literal["train", "dev", "test"]
Partition = Literal[
    "train_fit", "audit_holdout", "dev_select", "dev_calibrate", "test", "quarantine"
]


class FrozenContract(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ReceiptQuestion(FrozenContract):
    """Safe output for question-only consumers; has no label-related fields."""

    archive_sha256: SHA256
    source_split: SourceSplit
    source_image_id: SourceID
    source_question_id: SourceID
    source_row_index: SourceID
    filename: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    qid: str = Field(min_length=1)
    question_raw: str = Field(min_length=1, repr=False)
    question_nfc: str = Field(min_length=1, repr=False)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if value in {".", ".."} or any(c in value for c in '/\\:\x00<>"|?*'):
            raise ValueError("filename must be a relative basename")
        if value != value.strip() or value.endswith("."):
            raise ValueError("filename has unsafe boundary characters")
        return value

    @model_validator(mode="after")
    def check_identity(self) -> "ReceiptQuestion":
        expected = f"receiptvqa:{self.archive_sha256}:image:{self.source_image_id}"
        if (
            self.document_id != expected
            or self.qid != f"{expected}:question:{self.source_question_id}"
        ):
            raise ValueError("IDs must match the archive namespace and source IDs")
        if not self.question_raw.strip():
            raise ValueError("question must not be blank")
        if self.question_nfc != unicodedata.normalize("NFC", self.question_raw):
            raise ValueError("question_nfc must preserve raw question except NFC composition")
        return self


class ReceiptAssignment(FrozenContract):
    source_image_id: SourceID
    source_split: SourceSplit
    duplicate_group_id: str = Field(min_length=1)
    partition: Partition
    gold_for_training: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def check_role(self) -> "ReceiptAssignment":
        permitted = {
            "train": {"train_fit", "audit_holdout", "quarantine"},
            "dev": {"dev_select", "dev_calibrate", "quarantine"},
            "test": {"test"},
        }
        if self.partition not in permitted[self.source_split]:
            raise ValueError("partition is incompatible with the official source split")
        if self.gold_for_training and self.partition != "train_fit":
            raise ValueError("only train_fit may expose training gold")
        if not self.duplicate_group_id.strip():
            raise ValueError("duplicate group must not be blank")
        return self


class ReceiptAccessPlan(FrozenContract):
    """Caller-provided partition manifest, not an automatic split or proof of dedup."""

    archive_sha256: SHA256
    grouping_status: Literal["receipt_only", "image_dedup_verified", "conservative_candidate_graph"]
    image_inventory_sha256: SHA256 | None = None
    candidate_graph_sha256: SHA256 | None = None
    assignments: tuple[ReceiptAssignment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_groups(self) -> "ReceiptAccessPlan":
        if self.grouping_status == "conservative_candidate_graph" and (
            self.image_inventory_sha256 is None or self.candidate_graph_sha256 is None
        ):
            raise ValueError("conservative grouping requires inventory and graph provenance")
        images, groups = set(), {}
        for entry in self.assignments:
            if entry.source_image_id in images:
                raise ValueError("image IDs must have exactly one assignment")
            images.add(entry.source_image_id)
            if entry.partition == "quarantine":
                continue
            policy = (entry.partition, entry.gold_for_training)
            if entry.duplicate_group_id in groups and groups[entry.duplicate_group_id] != policy:
                raise ValueError("a duplicate group cannot cross partitions or gold selections")
            groups[entry.duplicate_group_id] = policy
        return self


class GoldReference(FrozenContract):
    """Explicit evaluator/training gold; serialization is privileged, not redacted."""

    qid: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    answers: tuple[str, ...] = Field(min_length=1, repr=False)

    @field_validator("answers")
    @classmethod
    def valid_answers(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("answerable references must be nonblank full alternatives")
        return values


class SupervisedReceiptExample(FrozenContract):
    question: ReceiptQuestion
    reference: GoldReference = Field(repr=False)

    @model_validator(mode="after")
    def check_join(self) -> "SupervisedReceiptExample":
        if self.question.source_split != "train":
            raise ValueError("supervised training examples require official train data")
        if (self.reference.qid, self.reference.document_id) != (
            self.question.qid,
            self.question.document_id,
        ):
            raise ValueError("gold reference does not match the question identity")
        return self
