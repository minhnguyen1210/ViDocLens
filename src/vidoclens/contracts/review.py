"""Explicit annotation provenance: AI review never silently becomes human gold."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.models import Box


class TranscriptionLine(FrozenContract):
    line_id: str = Field(min_length=1)
    reference: str = Field(min_length=1, repr=False)
    legibility: Literal["readable", "uncertain"]


class TranscriptionReview(FrozenContract):
    document_id: str = Field(min_length=1)
    image_sha256: SHA256
    ocr_sha256: SHA256
    reviewer: str = Field(min_length=1)
    reviewer_type: Literal["human", "ai"]
    reference_origin: Literal["image_transcription"]
    blind_to_ocr_during_transcription: bool = Field(strict=True)
    human_verified: bool = Field(strict=True)
    coverage: Literal["selected_lines", "full_image"]
    lines: tuple[TranscriptionLine, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_review(self):
        if self.reviewer_type == "ai" and self.human_verified:
            raise ValueError("AI review cannot claim human verification")
        if len({r.line_id for r in self.lines}) != len(self.lines):
            raise ValueError("duplicate transcription line IDs")
        return self


class OODAnnotation(FrozenContract):
    document_id: str = Field(min_length=1)
    image_sha256: SHA256
    rights_evidence_id: str = Field(min_length=1)
    source_domain: str = Field(min_length=1)
    shift_axes: tuple[str, ...] = Field(min_length=1)
    question: str = Field(min_length=1, repr=False)
    question_type: str = Field(min_length=1)
    answerable: bool = Field(strict=True)
    full_answers: tuple[str, ...] = Field(default=(), repr=False)
    evidence_boxes: tuple[Box, ...] = ()
    annotator_type: Literal["human", "ai"]
    annotator: str = Field(min_length=1)
    second_review: Literal["pending", "independent_human", "delayed_blind_same_human", "ai_only"]
    external_processing_allowed: Literal[False] = False
    eligible_as_human_gold: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def gold_boundary(self):
        if self.answerable and (not self.full_answers or not self.evidence_boxes):
            raise ValueError("answerable QA needs full answers and evidence")
        if any(not a.strip() for a in self.full_answers):
            raise ValueError("blank answers are invalid")
        if not self.answerable and (self.full_answers or self.evidence_boxes):
            raise ValueError("unanswerable QA must not invent answers or evidence")
        if self.eligible_as_human_gold and (
            self.annotator_type != "human"
            or self.second_review not in {"independent_human", "delayed_blind_same_human"}
        ):
            raise ValueError("human gold needs actual human annotation and review")
        return self
