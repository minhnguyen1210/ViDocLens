"""Lossless strict per-item parsing provenance for an immutable local generation run."""

from typing import Literal

from pydantic import Field

from vidoclens.contracts.dataset import SHA256, FrozenContract


class SilverReparseManifest(FrozenContract):
    protocol: Literal["strict_item_reparse_v1"] = "strict_item_reparse_v1"
    complete: Literal[True] = True
    source_run: str = Field(min_length=1)
    source_manifest_sha256: SHA256
    source_plan_sha256: SHA256
    source_batch_sha256: SHA256
    parsed_batch_sha256: SHA256
    parser_sha256: SHA256
    fixture_only: bool = Field(strict=True)
    raw_answers_modified: Literal[False] = False
    new_model_calls: Literal[0] = 0
    source_status_counts: dict[str, int]
    parsed_status_counts: dict[str, int]
