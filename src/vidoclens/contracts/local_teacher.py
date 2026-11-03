"""Local-only label generation. Permissions are owner attestations, not licenses."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract, ReceiptQuestion


class LocalTeacherConfig(FrozenContract):
    protocol: Literal["local_labels_image_only_v1"] = "local_labels_image_only_v1"
    model_id: str = Field(min_length=1)
    model_revision: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    snapshot_manifest_sha256: SHA256
    max_questions: int = Field(default=8, ge=1, le=32)
    max_question_characters: int = Field(default=12000, ge=128, le=32000)
    max_new_tokens: int = Field(default=2048, ge=64, le=8192)
    max_input_tokens: int = Field(default=8192, ge=256, le=32768)
    min_image_pixels: int = Field(default=4096, ge=1024)
    max_image_pixels: int = Field(default=262144, ge=4096, le=1048576)
    seed: int = Field(default=42, ge=0)
    do_sample: Literal[False] = False
    quantization: Literal["nf4_double_bfloat16"] = "nf4_double_bfloat16"
    attention: Literal["sdpa"] = "sdpa"
    part_protocol: Literal["whole_answer_v1", "literal_separator_v1"] = "whole_answer_v1"

    @model_validator(mode="after")
    def bounds(self):
        if self.min_image_pixels > self.max_image_pixels:
            raise ValueError("invalid pixel bounds")
        return self


class LocalTeacherRequest(FrozenContract):
    document_id: str = Field(min_length=1)
    image_sha256: SHA256
    questions: tuple[ReceiptQuestion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identity(self):
        if any(q.document_id != self.document_id for q in self.questions):
            raise ValueError("one image per local request")
        if len({q.qid for q in self.questions}) != len(self.questions):
            raise ValueError("duplicate request qid")
        return self


class LocalTeacherPlan(FrozenContract):
    protocol: Literal["local_label_plan_v1"] = "local_label_plan_v1"
    pool_sha256: SHA256
    access_plan_sha256: SHA256
    partition: Literal["train_fit", "dev_select", "audit_holdout"]
    fixture_only: bool = Field(strict=True)
    config: LocalTeacherConfig
    prompt_sha256: SHA256
    output_schema_sha256: SHA256
    implementation_sha256: SHA256
    requests: tuple[LocalTeacherRequest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def coverage(self):
        ids = [q.qid for r in self.requests for q in r.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate plan qid")
        for r in self.requests:
            if len(r.questions) > self.config.max_questions:
                raise ValueError("request exceeds question cap")
        return self


class LocalGenerationGrant(FrozenContract):
    plan_sha256: SHA256
    purpose: Literal["quality_pilot", "silver_generation"]
    generation_allowed: bool = Field(default=False, strict=True)
    data_rights_verified: bool = Field(default=False, strict=True)
    model_license_verified: bool = Field(default=False, strict=True)
    quality_pilot_passed: bool = Field(default=False, strict=True)
    evidence_sha256: SHA256
    approved_by: str = Field(min_length=1)


class LocalTeacherAnswer(FrozenContract):
    qid: str = Field(min_length=1)
    answer: str | None = Field(repr=False)
    evidence_text: str | None = Field(repr=False)
    answerable: bool = Field(strict=True)
    reason_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def state(self):
        if self.answerable:
            if self.answer is None or not self.answer.strip():
                raise ValueError("answerable needs a nonblank answer")
        elif self.answer is not None:
            raise ValueError("unanswerable cannot carry an answer")
        return self


class LocalTeacherOutput(FrozenContract):
    answers: tuple[LocalTeacherAnswer, ...]


class LocalGeneration(FrozenContract):
    """Exact decoded output, never a fabricated success on inference failure."""

    raw_text: str = Field(repr=False)
    status: Literal["completed", "incomplete", "error"]
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    generation_seconds: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    peak_reserved_bytes: int = Field(default=0, ge=0)


class LocalModelSnapshot(FrozenContract):
    model_id: str = Field(min_length=1)
    model_revision: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    files: dict[str, SHA256] = Field(min_length=1)
