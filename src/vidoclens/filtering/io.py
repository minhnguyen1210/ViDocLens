"""Canonical identities and immutable offline files; no credentials or model imports."""

import hashlib
import json
import os
import tempfile
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
    write_text_exclusive(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_text_exclusive(path: Path, payload: str):
    # Publish a complete file exclusively; os.replace would overwrite run evidence.
    # Hard links are supported by the project's NTFS/ext4 workspaces.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def revalidate(value):
    return type(value).model_validate(value.model_dump())
