"""Draft v1 contracts. Coordinate system: normalized [0, 1] after orientation correction."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class Split(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    OOD = "ood"
    QUARANTINE = "quarantine"


class Document(Contract):
    document_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    duplicate_group_id: str = Field(min_length=1)
    split: Split
    image_path: str = Field(min_length=1, description="Local dataset path; never an API input")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    rights_status: Literal["pending", "approved", "restricted"] = "pending"
    redacted: bool = False
    external_processing_allowed: bool = False


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    span_ids: list[str] = Field(default_factory=list)
    text: str | None = None
    support: Literal["exact", "fuzzy", "none", "not_checked"] = "not_checked"
    # OCR support is not a claim that the answer addresses the question correctly.
    verification_reason: str | None = None


class AnswerPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(
        min_length=1, description="One ordered part of a complete answer, not an alias"
    )
    evidence: Evidence = Field(default_factory=Evidence)

    @field_validator("text")
    @classmethod
    def check_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer parts require nonblank text")
        return value


class QARecord(Contract):
    qid: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answers: list[str] = Field(
        default_factory=list,
        description=(
            "Alternative FULL reference answers, not individual answer parts. Preserve each "
            "source serialization, including the ReceiptVQA separator ¡sep¿ and its whitespace."
        ),
    )
    answer_parts: list[list[AnswerPart]] = Field(
        default_factory=list,
        description=(
            "Optional parsed view parallel to answers: one ordered part list per full alternative, "
            "with evidence for every part. Empty means not parsed. Never flatten alternatives "
            "or overwrite raw serialization; source-specific parsing is not implemented yet."
        ),
    )
    label_source: Literal["gold", "silver", "unlabeled"]
    question_type: str | None = None
    answer_type: Literal["numeric", "non_numeric", "hybrid", "unknown"] = "unknown"
    teacher_run_id: str | None = None

    @model_validator(mode="after")
    def check_labels(self) -> "QARecord":
        if self.label_source == "unlabeled" and (self.answers or self.answer_parts):
            raise ValueError("unlabeled records must not contain reference answers or parts")
        if self.answer_parts and len(self.answer_parts) != len(self.answers):
            raise ValueError("answer_parts must align with the full reference alternatives")
        if any(not parts for parts in self.answer_parts):
            raise ValueError("each parsed reference must contain at least one answer part")
        return self


class TeacherQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qid: str = Field(min_length=1)
    question: str = Field(min_length=1)


class TeacherInput(Contract):
    """Label-free handoff; adapters must construct this instead of serializing QARecord."""

    document_id: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    questions: list[TeacherQuestion] = Field(min_length=1)
    ocr_text: str | None = None


class TeacherLabel(BaseModel):
    """Draft canonical output; provider-specific JSON Schema adaptation remains future work."""

    model_config = ConfigDict(extra="forbid")
    qid: str = Field(min_length=1)
    answer: str | None = Field(
        description="Complete raw answer; preserve ordered source parts and separator ¡sep¿"
    )
    evidence_text: str | None
    answerable: bool
    reason_code: str | None

    @model_validator(mode="after")
    def check_answerability(self) -> "TeacherLabel":
        if self.answerable and (self.answer is None or not self.answer.strip()):
            raise ValueError("answerable labels require a nonblank answer")
        if not self.answerable and self.answer is not None:
            raise ValueError("unanswerable labels must have answer=null")
        if not self.answerable and (self.reason_code is None or not self.reason_code.strip()):
            raise ValueError("unanswerable labels require a reason_code")
        return self


class Box(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_order(self) -> "Box":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("bounding box must have positive width and height")
        return self


class OCRSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    span_id: str = Field(min_length=1)
    text_raw: str
    text_nfc: str
    box: Box
    line_id: str
    reading_order: int = Field(ge=0)
    engine_score: float | None = Field(default=None, ge=0, le=1)


class OCRResult(Contract):
    document_id: str
    engine: str
    engine_revision: str
    preprocessing_hash: str
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["ok", "empty", "error"]
    spans: list[OCRSpan] = Field(default_factory=list)
    error_code: str | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    document_id: str
    qid: str
    question: str
    model_id: str
    model_revision: str
    prompt_hash: str
    config_hash: str
    ocr_cache_key: str | None = None


class Prediction(Contract):
    status: Literal["answered", "abstained", "error"]
    answer_raw: str | None = Field(
        default=None,
        description="Complete raw prediction; preserve separator ¡sep¿ for multipart answers",
    )
    answer_normalized: str | None = None
    answer_parts: list[AnswerPart] = Field(
        default_factory=list,
        description=(
            "Ordered parts of this ONE prediction with evidence per part; not alternative answers. "
            "Raw serialization is authoritative until the source evaluator/parser is verified."
        ),
    )
    evidence: Evidence = Field(default_factory=Evidence)
    backend: Literal["local", "openai", "cascade"]
    external_used: bool = False
    calibrated_confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def check_answer_status(self) -> "Prediction":
        if self.status == "answered" and (self.answer_raw is None or not self.answer_raw.strip()):
            raise ValueError("answered predictions require a nonempty raw answer")
        if self.status != "answered" and (
            self.answer_raw is not None or self.answer_normalized is not None or self.answer_parts
        ):
            raise ValueError("abstained/error predictions must not contain an answer")
        if self.status != "answered" and not self.reason:
            raise ValueError("abstained/error predictions require a reason")
        return self
