"""Preregistered configuration, not authorization to open final gold or claim G5."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.verification import RoutingPolicy, VerifierProfile
from vidoclens.filtering.io import digest


class FinalSuitePlan(FrozenContract):
    protocol: Literal["phase5_final_suite_plan_v1"] = "phase5_final_suite_plan_v1"
    verifier: VerifierProfile
    routing: RoutingPolicy
    frozen_access_plan_sha256: SHA256
    test_image_ids: tuple[int, ...] = Field(min_length=1)
    ood_curation_sha256: SHA256
    evaluator_source_sha256: SHA256
    systems: dict[str, SHA256]
    primary_comparison: Literal["P2_vs_P1-size"] = "P2_vs_P1-size"
    additional_comparisons: tuple[
        Literal["P3-check_vs_P2", "P3-snap_vs_P3-check", "P4_vs_teacher-all"], ...
    ] = ("P3-check_vs_P2", "P3-snap_vs_P3-check", "P4_vs_teacher-all")
    fixture_only: bool = Field(strict=True)
    execution_enabled: Literal[False] = False
    g5_certified: Literal[False] = False

    @model_validator(mode="after")
    def boundary(self):
        if (
            self.verifier.status != "frozen_dev_select"
            or self.routing.status != "frozen_dev_calibrate"
        ):
            raise ValueError("preregistration requires frozen verifier and routing")
        if (
            self.fixture_only != self.verifier.binding.fixture_only
            or self.fixture_only != self.routing.fixture_only
        ):
            raise ValueError("fixture provenance mismatch")
        if (
            self.routing.verifier_profile_sha256 != digest(self.verifier)
            or self.frozen_access_plan_sha256 != self.verifier.access_plan_sha256
            or self.systems.get("teacher-all") != self.verifier.binding.fallback_profile_sha256
            or self.verifier.binding.student_bundle_sha256
            not in [self.systems.get(f"P2/{seed}") for seed in (17, 42, 2026)]
        ):
            raise ValueError("frozen pipeline identity mismatch")
        required = {
            f"{arm}/{seed}" for arm in ("L2", "P1-full", "P1-size", "P2") for seed in (17, 42, 2026)
        } | {"teacher-all"}
        if (
            self.systems.keys() != required
            or len(set(self.test_image_ids)) != len(self.test_image_ids)
            or any(type(i) is not int or i < 0 for i in self.test_image_ids)
        ):
            raise ValueError("complete unique system/test membership required")
        if (
            set(self.additional_comparisons)
            != {"P3-check_vs_P2", "P3-snap_vs_P3-check", "P4_vs_teacher-all"}
            or len(self.additional_comparisons) != 3
        ):
            raise ValueError("all preregistered comparisons must be retained")
        return self
