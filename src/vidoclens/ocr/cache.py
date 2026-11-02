"""Content-addressed local OCR cache, with payload and configuration integrity."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from vidoclens.contracts.models import OCRResult


def cache_key(identity: dict) -> str:
    required = {
        "document_id",
        "raw_image_sha256",
        "canonical_pixel_sha256",
        "preprocessing",
        "language",
        "engine",
        "detector",
        "recognizer",
        "package_lock_sha256",
    }
    if set(identity) != required:
        raise ValueError("cache identity must contain every required dimension")
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_cache(directory: Path, identity: dict) -> OCRResult | None:
    key = cache_key(identity)
    path = directory / (key + ".json")
    if not path.exists():
        return None
    entry = json.loads(path.read_text(encoding="utf-8"))
    if entry["identity"] != identity or entry["key"] != key:
        raise ValueError("OCR cache identity mismatch")
    payload = json.dumps(entry["result"], sort_keys=True, ensure_ascii=False).encode()
    if hashlib.sha256(payload).hexdigest() != entry["payload_sha256"]:
        raise ValueError("OCR cache payload checksum mismatch")
    result = OCRResult.model_validate(entry["result"])
    if (
        result.document_id != identity["document_id"]
        or result.image_sha256 != identity["raw_image_sha256"]
    ):
        raise ValueError("OCR cache result image mismatch")
    return result


def store_cache(directory: Path, identity: dict, result: OCRResult) -> str:
    result = OCRResult.model_validate(result.model_dump())
    if (
        result.document_id != identity["document_id"]
        or result.image_sha256 != identity["raw_image_sha256"]
    ):
        raise ValueError("OCR result does not match cache identity")
    key = cache_key(identity)
    directory.mkdir(parents=True, exist_ok=True)
    previous = load_cache(directory, identity)
    if previous is not None:
        if previous != result:
            raise ValueError("immutable cache key has conflicting output")
        return key
    value = result.model_dump()
    entry = {
        "key": key,
        "identity": identity,
        "result": value,
        "payload_sha256": hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
    }
    fd, temporary = tempfile.mkstemp(prefix=".ocr-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(entry, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, directory / (key + ".json"))
        except FileExistsError:
            if load_cache(directory, identity) != result:
                raise ValueError("concurrent cache writer produced conflicting output") from None
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return key
