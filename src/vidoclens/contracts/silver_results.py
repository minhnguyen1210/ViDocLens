"""Trainer-independent result exchange; populated by the actual Phase 3 adapter."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.evaluation import AnswerPrediction


class SilverTrainingResult(FrozenContract):
    protocol: Literal["silver_training_result_v1"] = "silver_training_result_v1"
    arm: Literal["L2", "P1-full", "P1-size", "P2"]
    seed: Literal[17, 42, 2026]
    run_id: str = Field(min_length=1)
    fixture_only: bool = Field(strict=True)
    training_pool_sha256: SHA256
    evaluation_pool_sha256: SHA256
    selection_sha256: SHA256 | None
    training_profile_sha256: SHA256
    evaluation_profile_sha256: SHA256
    g3_evidence_sha256: SHA256
    checkpoint_sha256: SHA256
    optimizer_updates_completed: int = Field(gt=0)
    gold_qids: tuple[str, ...] = Field(min_length=1)
    silver_qids: tuple[str, ...] = ()
    gold_exposure_counts: dict[str, Annotated[int, Field(ge=0)]]
    silver_exposure_counts: dict[str, Annotated[int, Field(ge=0)]]
    equal_loss_weights: Literal[True] = True
    training_seconds: float = Field(gt=0, allow_inf_nan=False)
    peak_reserved_bytes: int = Field(gt=0)
    predictions: tuple[AnswerPrediction, ...]

    @model_validator(mode="after")
    def boundaries(self):
        if len(set(self.gold_qids)) != len(self.gold_qids) or len(set(self.silver_qids)) != len(
            self.silver_qids
        ):
            raise ValueError("duplicate training membership")
        if set(self.gold_qids) & set(self.silver_qids):
            raise ValueError("gold and silver membership overlap")
        if set(self.gold_exposure_counts) != set(self.gold_qids) or set(
            self.silver_exposure_counts
        ) != set(self.silver_qids):
            raise ValueError(
                "exposure logs must cover exactly selected membership, including zeros"
            )
        gold, silver = (
            sum(self.gold_exposure_counts.values()),
            sum(self.silver_exposure_counts.values()),
        )
        if not gold:
            raise ValueError("no measured gold exposures")
        if self.arm == "L2":
            if self.silver_qids or silver or self.selection_sha256 is not None:
                raise ValueError("L2 is gold-only")
        elif not self.silver_qids or self.selection_sha256 is None or gold != silver:
            raise ValueError("silver arms need selection binding and measured 1:1 exposures")
        if len({p.qid for p in self.predictions}) != len(self.predictions):
            raise ValueError("duplicate prediction qid")
        return self
