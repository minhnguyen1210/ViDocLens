"""Phase 5 exchange contracts. Scores are rules, never calibrated probabilities."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.models import Box, OCRResult
from vidoclens.contracts.silver import SilverSample

Rate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, strict=True)]


class PipelineBinding(FrozenContract):
    student_bundle_sha256: SHA256
    student_protocol_sha256: SHA256
    filter_config_sha256: SHA256
    fallback_profile_sha256: SHA256
    g4_evidence_sha256: SHA256
    fixture_only: bool = Field(strict=True)


class VerificationPool(FrozenContract):
    protocol: Literal["verification_dev_pool_v1"] = "verification_dev_pool_v1"
    partition: Literal["dev_select", "dev_calibrate"]
    archive_sha256: SHA256
    access_plan_sha256: SHA256
    inventory_sha256: SHA256
    samples: tuple[SilverSample, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identity(self):
        seen, documents = set(), {}
        for s in self.samples:
            q = s.question
            if q.qid in seen or q.archive_sha256 != self.archive_sha256 or q.source_split != "dev":
                raise ValueError("invalid dev membership/archive")
            seen.add(q.qid)
            identity = (s.image_sha256, s.duplicate_group_id)
            if q.document_id in documents and documents[q.document_id] != identity:
                raise ValueError("inconsistent document identity")
            documents[q.document_id] = identity
        return self


class VerifierConfig(FrozenContract):
    protocol: Literal["field_lexical_verifier_v1"] = "field_lexical_verifier_v1"
    text_threshold: Literal[0.0, 0.05, 0.10, 0.15] = 0.10
    min_text_length: int = Field(default=6, ge=2, le=100)
    candidate_margin: float = Field(default=0.05, gt=0, le=1, allow_inf_nan=False)
    max_label_gap: float = Field(default=0.08, gt=0, le=0.25, allow_inf_nan=False)
    max_span_line_gap: float = Field(default=0.08, gt=0, le=0.25, allow_inf_nan=False)
    max_document_tokens: int = Field(default=4096, ge=1, le=16384)
    max_span_tokens: int = Field(default=24, ge=1, le=64)
    max_lines: int = Field(default=4, ge=1, le=8)
    max_answer_characters: int = Field(default=1024, ge=1, le=4096)
    part_protocol: Literal["whole_answer_v1", "literal_separator_v1"] = "whole_answer_v1"
    require_field_support: Literal[True] = True
    numeric_edits_allowed: Literal[False] = False


class VerifierProfile(FrozenContract):
    config: VerifierConfig
    binding: PipelineBinding
    access_plan_sha256: SHA256
    implementation_sha256: SHA256
    status: Literal["candidate", "frozen_dev_select"] = "candidate"
    selection_evidence_sha256: SHA256 | None = None

    @model_validator(mode="after")
    def freeze(self):
        if (self.status == "frozen_dev_select") != (self.selection_evidence_sha256 is not None):
            raise ValueError("frozen verifier needs dev_select evidence")
        return self


class VerifierInput(FrozenContract):
    sample: SilverSample
    prediction: AnswerPrediction
    ocr: OCRResult | None = None

    @model_validator(mode="after")
    def identity(self):
        if self.prediction.qid != self.sample.question.qid:
            raise ValueError("prediction qid mismatch")
        if self.ocr is not None and (
            self.ocr.document_id != self.sample.question.document_id
            or self.ocr.image_sha256 != self.sample.image_sha256
        ):
            raise ValueError("OCR document/image mismatch")
        return self


class VerifierCandidate(FrozenContract):
    text: str = Field(min_length=1, repr=False)
    span_ids: tuple[str, ...] = Field(min_length=1)
    boxes: tuple[Box, ...] = Field(min_length=1)
    token_start: Count
    token_end: int = Field(gt=0, strict=True)
    distance: Rate
    field_status: Literal["pass", "fail", "unknown"]
    field_label_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence(self):
        if self.token_end <= self.token_start or len(self.boxes) != len(self.span_ids):
            raise ValueError("invalid candidate occurrence")
        return self


class VerifierPart(FrozenContract):
    before: str = Field(repr=False)
    after: str | None = Field(default=None, repr=False)
    selected: VerifierCandidate | None = None
    alternatives: tuple[VerifierCandidate, ...] = ()
    reason: str


class VerificationDecision(FrozenContract):
    qid: str
    input_sha256: SHA256
    config_sha256: SHA256
    implementation_sha256: SHA256
    variant: Literal["P3-check", "P3-snap"]
    status: Literal["answered", "abstained"]
    answer_before: str | None = Field(repr=False)
    answer_after: str | None = Field(default=None, repr=False)
    question_field: str
    parts: tuple[VerifierPart, ...] = ()
    reason: str
    snap_applied: bool = False
    rule_score: Rate = 0.0
    calibrated_confidence: None = None

    @model_validator(mode="after")
    def state(self):
        if self.status == "answered":
            if (
                not self.answer_after
                or not self.parts
                or any(p.selected is None or p.selected.field_status != "pass" for p in self.parts)
            ):
                raise ValueError("answered verifier result needs field-supported evidence")
        elif self.answer_after is not None or self.snap_applied or self.rule_score:
            raise ValueError("abstention has no final answer, applied snap or score")
        if self.snap_applied and (
            self.variant != "P3-snap" or self.answer_before == self.answer_after
        ):
            raise ValueError("invalid snap trace")
        if (
            self.status == "answered"
            and (self.answer_before != self.answer_after) != self.snap_applied
        ):
            raise ValueError("every answer edit must be an explicit snap")
        return self


class PredictionObservation(FrozenContract):
    prediction: AnswerPrediction
    cost_micro_usd: Count | None = None
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    external_requests: Count | None = None
    image_transmissions: Count | None = None


class VerificationBatch(FrozenContract):
    protocol: Literal["verification_predictions_v1"] = "verification_predictions_v1"
    pool_sha256: SHA256
    binding: PipelineBinding
    source: Literal["student", "fallback_teacher"]
    cache_regime: Literal["cache_miss", "cache_hit", "synthetic"]
    observations: tuple[PredictionObservation, ...]

    @model_validator(mode="after")
    def identity(self):
        qids = [o.prediction.qid for o in self.observations]
        if len(qids) != len(set(qids)):
            raise ValueError("duplicate prediction qid")
        if (self.cache_regime == "synthetic") != self.binding.fixture_only:
            raise ValueError("cache/fixture provenance mismatch")
        for o in self.observations:
            if self.source == "student" and (
                o.cost_micro_usd not in (None, 0) or o.external_requests or o.image_transmissions
            ):
                raise ValueError("student must be local")
            if self.cache_regime == "cache_hit" and (
                o.external_requests or o.image_transmissions or o.cost_micro_usd not in (None, 0)
            ):
                raise ValueError("cache-hit replay must not claim new API usage")
        return self


class RoutingPolicy(FrozenContract):
    protocol: Literal["rule_routing_v1"] = "rule_routing_v1"
    min_local_score: Rate = 1.0
    request_timeout_seconds: float = Field(default=45, gt=0, le=120, allow_inf_nan=False)
    fallback_limit: Literal[1] = 1
    transport_retries: Literal[0] = 0
    status: Literal["candidate", "frozen_dev_calibrate"] = "candidate"
    verifier_profile_sha256: SHA256
    implementation_sha256: SHA256
    selection_evidence_sha256: SHA256 | None = None
    fixture_only: bool = Field(strict=True)

    @model_validator(mode="after")
    def freeze(self):
        if (self.status == "frozen_dev_calibrate") != (self.selection_evidence_sha256 is not None):
            raise ValueError("frozen routing needs dev_calibrate evidence")
        return self
