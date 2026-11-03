"""Reference-free OOD review exchange; human work cannot be filled by fixtures/AI."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.models import Box


class OODReviewTask(FrozenContract):
    qid: str
    document_id: str
    image_sha256: SHA256
    canonical_pixel_sha256: SHA256
    source_domain: str = Field(min_length=1)
    shift_axes: tuple[str, ...] = Field(min_length=1)
    rights_evidence_sha256: SHA256
    question: str = Field(min_length=1, repr=False)
    question_type: str = Field(min_length=1)
    previously_model_reviewed: Literal[False] = False

    @model_validator(mode="after")
    def identity(self):
        if self.document_id.startswith("receiptvqa:") or not self.qid.startswith(
            self.document_id + ":question:"
        ):
            raise ValueError("OOD requires an external source identity")
        return self


class OODReviewPlan(FrozenContract):
    protocol: Literal["human_ood_plan_v1"] = "human_ood_plan_v1"
    fixture_only: bool = Field(strict=True)
    protected_inventory_sha256: SHA256
    dedup_evidence_sha256: SHA256
    unresolved_near_duplicates: Literal[0] = 0
    local_research_rights_attested: bool = Field(default=False, strict=True)
    seed: int = 42
    second_review_fraction: float = Field(default=0.20, ge=0.20, le=1, allow_inf_nan=False)
    tasks: tuple[OODReviewTask, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def identity(self):
        if len({r.qid for r in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate OOD qid")
        documents = {}
        for r in self.tasks:
            value = (
                r.image_sha256,
                r.canonical_pixel_sha256,
                r.source_domain,
                r.shift_axes,
                r.rights_evidence_sha256,
            )
            if r.document_id in documents and documents[r.document_id] != value:
                raise ValueError("inconsistent OOD document provenance")
            documents[r.document_id] = value
        return self


class OODHumanLabel(FrozenContract):
    qid: str
    answerable: bool = Field(strict=True)
    full_answers: tuple[str, ...] = ()
    evidence_boxes: tuple[Box, ...] = ()

    @model_validator(mode="after")
    def state(self):
        if self.answerable and (
            not self.full_answers
            or not self.evidence_boxes
            or any(not a.strip() for a in self.full_answers)
        ):
            raise ValueError("answerable human label needs full answers and evidence")
        if not self.answerable and (self.full_answers or self.evidence_boxes):
            raise ValueError("unanswerable label cannot invent evidence")
        return self


class OODHumanSubmission(FrozenContract):
    packet_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    reviewer: str = Field(min_length=1)
    reviewer_type: Literal["human"] = "human"
    reviewed_at: datetime
    blind_image_review_attested: bool = Field(strict=True)
    labels: tuple[OODHumanLabel, ...]

    @model_validator(mode="after")
    def state(self):
        if (
            not self.reviewer.strip()
            or not self.blind_image_review_attested
            or self.reviewed_at.utcoffset() is None
        ):
            raise ValueError("human identity, timezone timestamp and blind image review required")
        if len({r.qid for r in self.labels}) != len(self.labels):
            raise ValueError("duplicate human labels")
        return self


class OODResolution(FrozenContract):
    qid: str
    primary_label_sha256: SHA256
    second_label_sha256: SHA256
    final_label: OODHumanLabel
    reviewer: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    human_image_adjudication_attested: Literal[True]

    @model_validator(mode="after")
    def identity(self):
        if (
            self.qid != self.final_label.qid
            or not self.reviewer.strip()
            or not self.rationale.strip()
        ):
            raise ValueError("invalid human adjudication")
        return self
