"""Executable Phase 4 recipe; the Phase 3 gold-only contract remains unchanged."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.student import StudentConfig, StudentTrainingExample


class DistillationConfig(FrozenContract):
    protocol: Literal["phase4_matched_v1"] = "phase4_matched_v1"
    student: StudentConfig
    optimizer_updates: Literal[191] = 191
    checkpoint_steps: tuple[Literal[96, 191], ...] = (96, 191)
    gold_silver_ratio: Literal["1:1"] = "1:1"
    sampler: Literal["independent_cyclic_shuffle_alternating_v1"] = (
        "independent_cyclic_shuffle_alternating_v1"
    )
    examples_per_source: Literal[1528] = 1528
    historical_l2_examples: Literal[3053] = 3053
    evaluation_cohort_sha256: SHA256
    g3_evidence_sha256: SHA256

    @model_validator(mode="after")
    def fixed_recipe(self):
        base = self.student
        if (
            base.protocol != "phase3_gold_v2"
            or base.gradient_accumulation != 16
            or self.checkpoint_steps != (96, 191)
            or base.epochs != 1
        ):
            raise ValueError("Phase 4 requires the validated Phase 3 v2 update recipe")
        return self


class DistillationExample(StudentTrainingExample):
    source: Literal["gold", "silver"]


class DistillationPlan(FrozenContract):
    protocol: Literal["phase4_training_plan_v1"] = "phase4_training_plan_v1"
    arm: Literal["P1-full", "P1-size", "P2"]
    seed: Literal[17, 42, 2026]
    complete: Literal[True] = True
    fixture_only: Literal[False] = False
    split_sha256: SHA256
    environment_lock_sha256: SHA256
    g3_evidence_sha256: SHA256
    selection_sha256: SHA256
    training_profile_sha256: SHA256
    evaluation_pool_sha256: SHA256
    bundle_path: str = Field(min_length=1)
    approval_path: str = Field(min_length=1)
    files: dict[str, SHA256] = Field(min_length=1)
    dependencies: dict[str, SHA256] = Field(min_length=1)
    source_hashes: dict[str, SHA256] = Field(min_length=1)
    gold_qa: int = Field(gt=0)
    silver_qa: int = Field(gt=0)
    dev_qa: int = Field(gt=0)
    gold_in_teacher_input: Literal[False] = False
    test_ood_calibrate_audit_used_for_training: Literal[False] = False


class Phase4Criteria(FrozenContract):
    phase3_preserved: bool = Field(strict=True)
    local_teacher_pilot: bool = Field(strict=True)
    full_silver_provenance: bool = Field(strict=True)
    frozen_filter_and_holdout_replay: bool = Field(strict=True)
    human_error_review: bool = Field(strict=True)
    matched_three_seed_training: bool = Field(strict=True)
    mixed_sampler_resume: bool = Field(strict=True)
    twelve_result_comparison: bool = Field(strict=True)
    code_checks: bool = Field(strict=True)
    restricted_data_boundaries: bool = Field(strict=True)


class Phase4GateReport(FrozenContract):
    gate: Literal["G4"] = "G4"
    status: Literal["pass", "incomplete"]
    criteria: Phase4Criteria
    evidence: dict[str, SHA256] = Field(min_length=1)
    h2_primary_difference: float = Field(allow_inf_nan=False)
    h2_positive_required: Literal[False] = False
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def honest_gate(self):
        values = self.criteria.model_dump(exclude={"schema_version"})
        if (self.status == "pass") != all(values.values()):
            raise ValueError("G4 status must reflect every evidence gate; H2 need not be positive")
        return self
