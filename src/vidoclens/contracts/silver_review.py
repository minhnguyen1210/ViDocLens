"""Blind audit packet and explicit human annotations; never replacement gold."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import SilverSample


class SilverReviewItem(FrozenContract):
    sample: SilverSample
    answer_raw: str = Field(min_length=1, repr=False)
    ocr: OCRResult | None


class SilverReviewPacket(FrozenContract):
    protocol: Literal["blind_silver_review_v1"] = "blind_silver_review_v1"
    pool_sha256: SHA256
    filter_run_sha256: SHA256
    audit_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    seed: int
    per_stratum: int = Field(gt=0)
    items: tuple[SilverReviewItem, ...]

    @model_validator(mode="after")
    def unique(self):
        qids = [i.sample.question.qid for i in self.items]
        if len(qids) != len(set(qids)):
            raise ValueError("duplicate review qid")
        return self


class SilverHumanJudgment(FrozenContract):
    qid: str = Field(min_length=1)
    correctness: Literal["correct", "wrong", "uncertain"]
    semantic_field: Literal["correct", "wrong", "uncertain"]
    ocr_quality: Literal["good", "partial", "unreadable", "uncertain"]
    error_tags: tuple[
        Literal[
            "ocr_miss",
            "wrong_field",
            "digit_error",
            "format_difference",
            "gold_disagreement",
            "unreadable_image",
            "other",
        ],
        ...,
    ] = ()
    note: str = Field(default="", repr=False)


class SilverHumanReview(FrozenContract):
    protocol: Literal["silver_human_review_v1"] = "silver_human_review_v1"
    packet_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    annotator_kind: Literal["human"] = "human"
    reviewer: str = Field(min_length=1)
    image_inspection_attested: bool = Field(strict=True)
    judgments: tuple[SilverHumanJudgment, ...]

    @model_validator(mode="after")
    def coverage(self):
        if not self.reviewer.strip() or not self.image_inspection_attested:
            raise ValueError("human review requires reviewer and image inspection attestation")
        if len({r.qid for r in self.judgments}) != len(self.judgments):
            raise ValueError("duplicate human judgment")
        return self
