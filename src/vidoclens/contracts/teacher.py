"""Phase 2 boundaries. Evaluation permission never grants training permission."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract

PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
Role = Literal["benchmark_teacher", "label_teacher", "fallback_teacher"]
Modality = Literal["ocr_text", "image", "image_ocr"]


class TeacherQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    qid: str = Field(min_length=1)
    question: str = Field(min_length=1, repr=False)


class TeacherProfile(FrozenContract):
    provider: Literal["openai"] = "openai"
    endpoint: Literal["/v1/responses"] = "/v1/responses"
    model_snapshot: str = Field(pattern=r"^gpt-[a-z0-9.\-]+-\d{4}-\d{2}-\d{2}$")
    role: Role
    modality: Modality
    prompt_version: Literal["teacher_vqa_v2"] = "teacher_vqa_v2"
    image_detail: Literal["high", "low"] = "high"
    max_output_tokens: PositiveInt = 4096
    reasoning_effort: Literal["none"] = "none"
    store: Literal[False] = False


class TeacherRequest(FrozenContract):
    """Question-only data. No general-purpose metadata or answer field is accepted."""

    archive_sha256: SHA256
    split_sha256: SHA256
    document_id: str = Field(min_length=1)
    source_image_id: NonnegativeInt
    partition: Literal["train_fit", "dev_select"]
    purpose: Literal["integration_pilot", "dev_baseline", "silver"]
    experiment: Literal["pilot", "A1", "A2", "A3", "A5", "silver"]
    image_sha256: SHA256
    image_path: str = Field(min_length=1)
    preprocessing: str = Field(min_length=1)
    ocr_text: str | None = Field(default=None, repr=False)
    ocr_sha256: SHA256 | None = None
    questions: tuple[TeacherQuery, ...] = Field(min_length=1)
    profile: TeacherProfile

    @model_validator(mode="after")
    def boundaries(self):
        if len({q.qid for q in self.questions}) != len(self.questions):
            raise ValueError("duplicate input qid")
        if any(not q.question.strip() or not q.qid.strip() for q in self.questions):
            raise ValueError("blank input question/qid")
        if self.profile.modality == "image":
            if self.ocr_text is not None or self.ocr_sha256 is not None:
                raise ValueError("image-only must not carry OCR")
        elif self.ocr_text is None or self.ocr_sha256 is None:
            raise ValueError("OCR modality requires text and provenance hash, including empty OCR")
        if self.purpose == "silver":
            if self.partition != "train_fit" or self.profile.role != "label_teacher":
                raise ValueError("silver requires train_fit and label_teacher")
            if self.experiment != "silver":
                raise ValueError("invalid silver experiment")
        elif self.profile.role != "benchmark_teacher":
            raise ValueError("Phase 2 evaluations require benchmark_teacher")
        if self.purpose == "dev_baseline" and self.partition != "dev_select":
            raise ValueError("baseline selection only permits dev_select")
        if self.purpose == "integration_pilot" and self.partition != "train_fit":
            raise ValueError("integration pilot is train_fit only")
        return self


class TeacherAnswer(BaseModel):
    """All fields required, including nulls, for the provider's strict JSON schema."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    qid: str
    answer: str | None = Field(repr=False)
    evidence_text: str | None = Field(repr=False)
    answerable: bool
    reason_code: str | None

    @model_validator(mode="after")
    def answer_state(self):
        if not self.qid.strip():
            raise ValueError("blank qid")
        if self.answerable:
            if self.answer is None or not self.answer.strip() or self.reason_code is not None:
                raise ValueError("answerable requires nonblank answer and null reason")
        elif self.answer is not None or self.reason_code is None or not self.reason_code.strip():
            raise ValueError("unanswerable requires null answer and a reason")
        return self


class TeacherOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    labels: list[TeacherAnswer]


class TeacherUsage(FrozenContract):
    input_tokens: NonnegativeInt
    cached_input_tokens: NonnegativeInt = 0
    output_tokens: NonnegativeInt
    total_tokens: NonnegativeInt

    @model_validator(mode="after")
    def counts(self):
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached tokens exceed input")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("inconsistent total usage")
        return self


class TeacherResult(FrozenContract):
    request_key: SHA256
    status: Literal[
        "ok",
        "refused",
        "incomplete",
        "schema_error",
        "qid_error",
        "provider_error",
        "transport_error",
        "model_mismatch",
        "usage_error",
    ]
    labels: tuple[TeacherAnswer, ...] = ()
    usage: TeacherUsage | None = None
    provider_response_id: str | None = None
    resolved_model: str | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def success(self):
        if self.status == "ok" and (not self.labels or self.usage is None):
            raise ValueError("successful response needs labels and usage")
        if self.status != "ok" and self.labels:
            raise ValueError("failed groups cannot publish partial labels")
        return self


class TeacherPermission(FrozenContract):
    provider: Literal["openai"] = "openai"
    archive_sha256: SHA256
    split_sha256: SHA256
    external_processing_allowed: bool = Field(default=False, strict=True)
    account_terms_reviewed: bool = Field(default=False, strict=True)
    retention_reviewed: bool = Field(default=False, strict=True)
    batch_files_allowed: bool = Field(default=False, strict=True)
    training_export_allowed: bool = Field(default=False, strict=True)
    approved_by: str | None = None
    approved_at: str | None = None
    evidence: str | None = None
    budget_micro_usd: NonnegativeInt = 0
    price_snapshot_approved: bool = Field(default=False, strict=True)
    allowed_models: tuple[str, ...] = ()
    allowed_request_keys: tuple[SHA256, ...] = ()


class TeacherPriceCard(FrozenContract):
    """Integer nano-USD/token; full input limit is a conservative reservation bound."""

    model_snapshot: str
    checked_at: str
    source_url: str
    source_sha256: SHA256
    input_nano_usd: PositiveInt
    cached_input_nano_usd: PositiveInt
    output_nano_usd: PositiveInt
    max_input_tokens: PositiveInt
    max_output_tokens: PositiveInt
    long_context_threshold: PositiveInt | None = None
    long_input_multiplier: PositiveInt = 1
    long_output_multiplier_milli: PositiveInt = 1000

    @model_validator(mode="after")
    def prices(self):
        if self.cached_input_nano_usd > self.input_nano_usd:
            raise ValueError("cached input price exceeds regular price")
        return self
