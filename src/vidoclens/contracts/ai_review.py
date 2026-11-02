"""Explicit AI-only annotation and reference-free reviewer inputs for ADR-021."""

from typing import Literal

from pydantic import Field, model_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract
from vidoclens.contracts.models import Box
from vidoclens.contracts.review import OODAnnotation


class OODSeedDocument(FrozenContract):
    document_id: str = Field(min_length=1)
    page_id: int = Field(gt=0)
    page_revision: int = Field(gt=0)
    source_url: str = Field(pattern=r"^https://commons\.wikimedia\.org/")
    original_url: str = Field(pattern=r"^https://upload\.wikimedia\.org/")
    author_credit: str = Field(min_length=1)
    license_id: Literal["CC0", "CC BY 2.0", "CC BY-SA 4.0"]
    license_url: str = Field(pattern=r"^https?://creativecommons\.org/")
    rights_evidence_id: str = Field(min_length=1)
    metadata_sha256: SHA256
    metadata_path: str = Field(min_length=1)
    raw_path: str = Field(min_length=1)
    image_path: str = Field(min_length=1)
    raw_image_sha256: SHA256
    processed_image_sha256: SHA256
    canonical_pixel_sha256: SHA256
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    document_kind: str = Field(min_length=1)
    shift_axes: tuple[str, ...] = Field(min_length=1)
    source_caveats: tuple[str, ...]
    partition: Literal["ood_seed", "quarantine"]
    local_research_allowed: Literal[True] = True
    external_processing_allowed: Literal[False] = False
    publication_approved: Literal[False] = False

    @model_validator(mode="after")
    def identity(self):
        if self.document_id != f"commons:{self.page_id}:{self.raw_image_sha256}":
            raise ValueError("document identity must bind page and downloaded bytes")
        if self.rights_evidence_id != f"commons:{self.page_id}:revision:{self.page_revision}":
            raise ValueError("rights evidence must bind the source page revision")
        return self


class OODSeedQA(OODAnnotation):
    qid: str = Field(min_length=1)
    reference_tier: Literal["ai_reference"] = "ai_reference"
    partition: Literal["ood_seed"] = "ood_seed"
    eligible_for_training: Literal[False] = False
    eligible_for_confirmatory_evaluation: Literal[False] = False

    @model_validator(mode="after")
    def identity_and_tier(self):
        if not self.qid.startswith(self.document_id + ":question:"):
            raise ValueError("qid must be namespaced to the source document")
        if self.annotator_type != "ai" or self.eligible_as_human_gold:
            raise ValueError("AI seed cannot be represented as human gold")
        return self


class AIReviewTask(FrozenContract):
    """No answer, reference, draft-label or OCR fields are accepted."""

    task_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    image_path: str = Field(min_length=1)
    image_sha256: SHA256
    kind: Literal["ocr_transcription", "ood_annotation_check"]
    question: str = Field(min_length=1, max_length=2000, repr=False)
    crop: Box | None = None


class AIReviewOutput(FrozenContract):
    task_id: str = Field(min_length=1)
    input_image_sha256: SHA256
    raw_text: str = Field(repr=False)
    generated_tokens: int = Field(ge=0)
    truncated: bool = Field(strict=True)
    status: Literal["ok", "empty", "error"]
    seconds: float = Field(ge=0)
    peak_allocated_bytes: int = Field(ge=0)


class AIAdjudication(FrozenContract):
    task_id: str = Field(min_length=1)
    reviewer_output_sha256: SHA256
    final_record_sha256: SHA256
    decision: Literal["confirmed_from_image", "corrected_from_image", "uncertain_excluded"]
    rationale: str = Field(min_length=1)
    adjudicator: Literal["Codex assistant"] = "Codex assistant"
    human_verified: Literal[False] = False
