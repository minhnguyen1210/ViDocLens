"""New fallback boundary; never expands the Phase 2 benchmark grant."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import SilverSample
from vidoclens.contracts.verification import Count, PipelineBinding, VerificationDecision


class FallbackRequest(FrozenContract):
    protocol: Literal["verified_fallback_request_v1"] = "verified_fallback_request_v1"
    sample: SilverSample
    ocr: OCRResult
    binding: PipelineBinding
    max_transport_attempts: Literal[1] = 1

    @model_validator(mode="after")
    def identity(self):
        if (
            self.ocr.document_id != self.sample.question.document_id
            or self.ocr.image_sha256 != self.sample.image_sha256
        ):
            raise ValueError("fallback OCR/sample identity mismatch")
        return self


class ExternalGate(FrozenContract):
    server_external_enabled: bool = Field(default=False, strict=True)
    request_allow_external: bool = Field(default=False, strict=True)
    document_may_external_process: bool = Field(default=False, strict=True)
    provider_healthy: bool = Field(default=False, strict=True)
    permission_evidence_sha256: SHA256 | None = None
    allowed_request_sha256: SHA256 | None = None
    reserve_micro_usd: Count = 0


class FallbackReply(FrozenContract):
    request_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    status: Literal["completed", "timeout", "provider_error", "invalid_schema"]
    prediction: AnswerPrediction | None = None
    raw_response_sha256: SHA256 | None = None
    actual_cost_micro_usd: Count | None = None

    @model_validator(mode="after")
    def state(self):
        if self.status == "completed" and (
            self.prediction is None or self.raw_response_sha256 is None
        ):
            raise ValueError("completed fallback needs parsed prediction and raw response hash")
        if self.status != "completed" and self.prediction is not None:
            raise ValueError("failed fallback must not expose an answer")
        return self


class CascadeOutcome(FrozenContract):
    status: Literal["answered", "abstained"]
    answer: str | None = Field(default=None, repr=False)
    source: Literal["student", "teacher", "none"]
    reason: str
    student: VerificationDecision
    teacher: VerificationDecision | None = None
    external_attempted: bool = False
    cache_hit: bool = False
    calibrated_confidence: None = None

    @model_validator(mode="after")
    def state(self):
        if self.status == "answered" and (not self.answer or self.source == "none"):
            raise ValueError("answered cascade needs a source and answer")
        if self.status == "abstained" and (self.answer is not None or self.source != "none"):
            raise ValueError("abstention has no answer/source")
        if self.cache_hit and self.external_attempted:
            raise ValueError("cache replay must not claim a new external attempt")
        if self.status == "answered":
            evidence = self.student if self.source == "student" else self.teacher
            if (
                evidence is None
                or evidence.status != "answered"
                or self.answer != evidence.answer_after
            ):
                raise ValueError("final answer must match verified source evidence")
        if self.source == "student" and (self.external_attempted or self.cache_hit):
            raise ValueError("local answer cannot claim fallback usage")
        return self
