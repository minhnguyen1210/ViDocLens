"""Canonical identities and immutable offline files; no credentials or model imports."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel


def digest(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_model(path: Path, model):
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def write_model(path: Path, value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def revalidate(value):
    return type(value).model_validate(value.model_dump())
