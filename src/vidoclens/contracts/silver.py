"""Versioned offline exchange with a future local label runner and Phase 3 trainer."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract, ReceiptQuestion


class SilverSample(FrozenContract):
    question: ReceiptQuestion
    duplicate_group_id: str = Field(min_length=1)
    image_sha256: SHA256


class SilverPool(FrozenContract):
    protocol: Literal["silver_pool_v1"] = "silver_pool_v1"
    partition: Literal["train_fit", "dev_select", "audit_holdout"]
    archive_sha256: SHA256
    access_plan_sha256: SHA256
    inventory_sha256: SHA256
    evaluation_cohort_sha256: SHA256 | None = None
    gold_budget: Literal[10] = 10
    samples: tuple[SilverSample, ...] = Field(min_length=1)
    gold_samples: tuple[SilverSample, ...] = ()

    @model_validator(mode="after")
    def check_scope(self):
        if self.evaluation_cohort_sha256 is not None and self.partition != "dev_select":
            raise ValueError("evaluation cohort is dev_select only")
        if self.partition != "train_fit" and self.gold_samples:
            raise ValueError("nontraining pools cannot carry training membership")
        seen, documents = set(), {}
        for row in (*self.samples, *self.gold_samples):
            q = row.question
            source = "dev" if self.partition == "dev_select" else "train"
            if q.archive_sha256 != self.archive_sha256 or q.source_split != source:
                raise ValueError("question does not belong to pool archive/source")
            if q.qid in seen:
                raise ValueError("duplicate or overlapping pool qid")
            seen.add(q.qid)
            identity = (row.duplicate_group_id, row.image_sha256)
            if q.document_id in documents and documents[q.document_id] != identity:
                raise ValueError("inconsistent document image/group identity")
            documents[q.document_id] = identity
        if {r.duplicate_group_id for r in self.samples} & {
            r.duplicate_group_id for r in self.gold_samples
        }:
            raise ValueError("gold and silver groups overlap")
        return self


class SilverLabel(FrozenContract):
    qid: str = Field(min_length=1)
    status: Literal["answered", "unanswerable", "refused", "incomplete", "parse_error", "error"]
    answer_raw: str | None = Field(default=None, repr=False)
    evidence_text: str | None = Field(default=None, repr=False)
    raw_response_sha256: SHA256
    reason: str | None = None

    @model_validator(mode="after")
    def check_answer(self):
        if self.status == "answered":
            if self.answer_raw is None or not self.answer_raw.strip():
                raise ValueError("answered label needs a nonblank raw answer")
        elif self.answer_raw is not None or not self.reason or not self.reason.strip():
            raise ValueError("failed/unanswerable label needs reason and no answer")
        return self


class SilverBatch(FrozenContract):
    """Local runner result import only. API evaluation caches are not this format."""

    protocol: Literal["local_silver_batch_v1"] = "local_silver_batch_v1"
    provider: Literal["local_open_weight"] = "local_open_weight"
    fixture_only: bool = Field(default=False, strict=True)
    pool_sha256: SHA256
    run_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    prompt_sha256: SHA256
    generation_config_sha256: SHA256
    environment_sha256: SHA256
    part_protocol: Literal["whole_answer_v1", "literal_separator_v1"] = "whole_answer_v1"
    labels: tuple[SilverLabel, ...]

    @model_validator(mode="after")
    def unique_qids(self):
        if len({r.qid for r in self.labels}) != len(self.labels):
            raise ValueError("duplicate teacher qids")
        return self


class FilterConfig(FrozenContract):
    filter: Literal["F1"] = "F1"
    algorithm: Literal["lexical_f1_v1"] = "lexical_f1_v1"
    status: Literal["pilot_defaults_not_calibrated", "frozen_dev_select"] = (
        "pilot_defaults_not_calibrated"
    )
    freeze_evidence_sha256: SHA256 | None = None
    freeze_access_plan_sha256: SHA256 | None = None
    freeze_fixture_only: bool | None = Field(default=None, strict=True)
    text_max_normalized_edit_distance: Literal[0.0, 0.05, 0.10, 0.15] = 0.10
    min_fuzzy_characters: int = Field(default=6, ge=2, le=100)
    min_candidate_margin: float = Field(default=0.05, gt=0, le=1, allow_inf_nan=False)
    max_consecutive_lines: int = Field(default=3, ge=1, le=8)
    max_span_tokens: int = Field(default=24, ge=1, le=64)
    max_document_tokens: int = Field(default=4096, ge=1, le=16384)
    max_answer_characters: int = Field(default=1024, ge=1, le=4096)
    require_unique_candidate: Literal[True] = True
    allow_digit_edits: Literal[False] = False
    require_numeric_token_boundaries: Literal[True] = True
    use_question_field_compatibility: Literal[False] = False
    keep_raw_answer: Literal[True] = True
    fallback_on_ocr_failure: Literal["reject_with_reason"] = "reject_with_reason"

    @model_validator(mode="after")
    def freeze_binding(self):
        bindings = (
            self.freeze_evidence_sha256,
            self.freeze_access_plan_sha256,
            self.freeze_fixture_only,
        )
        if (
            self.status == "frozen_dev_select"
            and any(v is None for v in bindings)
            or self.status != "frozen_dev_select"
            and any(v is not None for v in bindings)
        ):
            raise ValueError("frozen rules require dev_select selection evidence")
        return self


class PartSupport(FrozenContract):
    text_raw: str = Field(min_length=1, repr=False)
    text_normalized: str = Field(min_length=1, repr=False)
    support: Literal["exact", "fuzzy", "none"]
    reason: str = Field(min_length=1)
    span_ids: tuple[str, ...] = ()
    token_start: int | None = Field(default=None, ge=0)
    token_end: int | None = Field(default=None, ge=1)
    distance: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    candidate_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def evidence_state(self):
        if self.support != "none":
            if (
                not self.span_ids
                or self.token_start is None
                or self.token_end is None
                or self.token_end <= self.token_start
                or self.distance is None
                or (self.support == "exact" and self.distance != 0)
            ):
                raise ValueError("supported parts need a valid OCR occurrence")
        return self


class FilterDecision(FrozenContract):
    qid: str
    sample_sha256: SHA256
    label_sha256: SHA256 | None
    answer_raw: str | None = Field(repr=False)
    answer_normalized: str | None = Field(repr=False)
    answer_type: Literal["numeric", "text", "hybrid", "unknown"]
    question_type: str
    f0_keep: bool
    f1_keep: bool
    reason: str
    parts: tuple[PartSupport, ...] = ()
    semantic_check: Literal["pass", "fail", "unknown"] = "unknown"
    semantic_reason: str = "semantic_checker_not_implemented"

    @model_validator(mode="after")
    def decision_state(self):
        if self.f0_keep and not (self.answer_raw and self.answer_raw.strip()):
            raise ValueError("F0 requires an answered label")
        if self.f1_keep and (
            not self.f0_keep or not self.parts or any(p.support == "none" for p in self.parts)
        ):
            raise ValueError("F1 requires support for every part and F0 eligibility")
        return self


class FilterRun(FrozenContract):
    protocol: Literal["silver_filter_run_v1"] = "silver_filter_run_v1"
    pool_sha256: SHA256
    batch_sha256: SHA256
    ocr_sha256: SHA256
    implementation_sha256: SHA256
    config: FilterConfig
    decisions: tuple[FilterDecision, ...]

    @model_validator(mode="after")
    def unique_decisions(self):
        if len({r.qid for r in self.decisions}) != len(self.decisions):
            raise ValueError("duplicate decisions")
        return self


class SilverApproval(FrozenContract):
    """Owner attestation for this exact local result, never inherited from Phase 2."""

    provider: Literal["local_open_weight"] = "local_open_weight"
    pool_sha256: SHA256
    batch_sha256: SHA256
    training_labels_allowed: bool = Field(default=False, strict=True)
    data_rights_verified: bool = Field(default=False, strict=True)
    model_license_verified: bool = Field(default=False, strict=True)
    quality_pilot_passed: bool = Field(default=False, strict=True)
    approved_by: str = Field(min_length=1)
    evidence_sha256: SHA256


class SilverExperiment(FrozenContract):
    protocol: Literal["silver_experiment_selection_v1"] = "silver_experiment_selection_v1"
    arm: Literal["P1-full", "P1-size", "P2"]
    seed: Literal[17, 42, 2026]
    pool_sha256: SHA256
    batch_sha256: SHA256
    filter_run_sha256: SHA256
    approval_sha256: SHA256
    training_profile_sha256: SHA256
    optimizer_updates: int = Field(gt=0)
    gold_qids: tuple[str, ...] = Field(min_length=1)
    silver_qids: tuple[str, ...] = Field(min_length=1)
    gold_silver_ratio: Literal["1:1"] = "1:1"
    equal_loss_weights: Literal[True] = True
    fixture_only: bool
    training_executed: Literal[False] = False
    requires_g3_validation: Literal[True] = True

    @model_validator(mode="after")
    def disjoint_unique(self):
        if (
            len(set(self.gold_qids)) != len(self.gold_qids)
            or len(set(self.silver_qids)) != len(self.silver_qids)
            or set(self.gold_qids) & set(self.silver_qids)
        ):
            raise ValueError("training membership must be unique and disjoint")
        return self
