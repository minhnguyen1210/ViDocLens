"""Immutable references for adopting completed runs after an evaluation pause."""

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator

from vidoclens.contracts.dataset import SHA256, FrozenContract


def relative_path(value: str) -> str:
    if (
        not value
        or "\\" in value
        or ":" in value
        or PurePosixPath(value).is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("expected a canonical workspace-relative POSIX path")
    return value


class Phase3EvidenceFile(FrozenContract):
    path: str
    sha256: SHA256

    _path = field_validator("path")(relative_path)


class Phase3RunEvidence(FrozenContract):
    directory: str
    files: dict[str, SHA256] = Field(min_length=2)

    _directory = field_validator("directory")(relative_path)

    @field_validator("files")
    @classmethod
    def safe_files(cls, value):
        for name in value:
            relative_path(name)
        if not {"run.json", "profile.json"} <= value.keys():
            raise ValueError("run and profile references required")
        return value


class Phase3Continuation(FrozenContract):
    protocol: Literal["phase3_continuation_v1"] = "phase3_continuation_v1"
    plan_sha256: SHA256
    parent_campaign: Phase3EvidenceFile
    pause_event: Phase3EvidenceFile
    execution: Phase3EvidenceFile
    runs: dict[str, Phase3RunEvidence] = Field(min_length=1)
    replaced_incomplete_runs: dict[str, Phase3RunEvidence] = Field(min_length=1)
