"""Strict, label-free inputs for the local feasibility pilot (not evaluation)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PilotReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    qid: str = Field(min_length=1)
    question_raw: str = Field(min_length=1)
    image_path: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mode: str
    duplicate_group_image_ids: list[int] = Field(min_length=1)
    exclude_from_future_audit_holdout: Literal[True]


class Phase0PilotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: str
    pilot: list[PilotReceipt] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_receipts(self) -> "Phase0PilotManifest":
        for field in ("document_id", "qid", "image_sha256"):
            if len({getattr(row, field) for row in self.pilot}) != len(self.pilot):
                raise ValueError(f"duplicate {field} in pilot")
        return self
