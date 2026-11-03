"""Offline routing search specification; no live API permission is conveyed."""

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.verification import Rate


class RoutingGridPlan(FrozenContract):
    pool_sha256: SHA256
    verifier_profile_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    thresholds: tuple[Rate, ...] = (0.0, 0.85, 0.90, 0.95, 1.0)
    external_eligible_qids: tuple[str, ...]
    target_local_coverage: Rate = 0.70
    target_cost_ratio: Rate = 0.40
    max_em_gap_to_teacher: Rate = 0.02

    @model_validator(mode="after")
    def unique(self):
        if not self.thresholds or tuple(sorted(set(self.thresholds))) != self.thresholds:
            raise ValueError("thresholds must be nonempty, sorted and unique")
        if len(set(self.external_eligible_qids)) != len(self.external_eligible_qids):
            raise ValueError("duplicate eligible qid")
        return self
