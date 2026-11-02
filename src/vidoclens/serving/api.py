"""CPU scaffold with real input validation and explicit unavailable inference."""

import io
import os
import warnings
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from vidoclens import __version__

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
Mode = Literal["local", "openai", "cascade"]

app = FastAPI(title="ViDocLens", version=__version__, description="Phase 0 foundation")


def fail(status: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


async def validate_image(image: UploadFile) -> None:
    """Bound file bytes, verify actual format, reject animation and oversized images."""
    try:
        if image.content_type not in ALLOWED_TYPES:
            fail(415, "unsupported_media_type", "Use JPEG, PNG or WEBP.")
        data = bytearray()
        while chunk := await image.read(64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_UPLOAD_BYTES:
                fail(413, "image_too_large", "Image must not exceed 10 MiB.")
        if not data:
            fail(422, "empty_image", "Image is empty.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as decoded:
                if decoded.format != ALLOWED_TYPES[image.content_type]:
                    fail(415, "image_type_mismatch", "Image bytes do not match the content type.")
                if decoded.width * decoded.height > MAX_IMAGE_PIXELS:
                    fail(413, "image_dimensions_too_large", "Image exceeds 20 million pixels.")
                if getattr(decoded, "n_frames", 1) > 1:
                    fail(415, "animated_image", "Use a single still image.")
                decoded.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(413, "image_dimensions_too_large", "Image dimensions are unsafe to decode.")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        fail(422, "invalid_image", "Image cannot be decoded.")
    finally:
        await image.close()


def validate_external(mode: Mode, allow_external: bool) -> None:
    if mode != "local" and not allow_external:
        fail(
            403, "external_processing_not_allowed", "Explicit external-processing consent required."
        )
    if mode != "local" and os.environ.get("VIDOCLENS_EXTERNAL_ENABLED", "false").lower() != "true":
        fail(403, "external_processing_disabled", "External processing is disabled on this server.")


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive", "stage": "foundation", "version": __version__}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "reason": "model_not_configured"},
    )


@app.post("/v1/vqa", status_code=501)
async def vqa(
    image: Annotated[UploadFile, File()],
    question: Annotated[str, Form(min_length=1, max_length=1000)],
    mode: Annotated[Mode, Form()] = "local",
    allow_external: Annotated[bool, Form()] = False,
) -> None:
    if not question.strip():
        await image.close()
        fail(422, "empty_question", "Question must contain text.")
    try:
        validate_external(mode, allow_external)
    except HTTPException:
        await image.close()
        raise
    await validate_image(image)
    fail(501, "inference_not_implemented", "Foundation only: no student or teacher adapter loaded.")


@app.post("/v1/extract", status_code=501)
async def extract(
    image: Annotated[UploadFile, File()],
    mode: Annotated[Mode, Form()] = "local",
    allow_external: Annotated[bool, Form()] = False,
) -> None:
    try:
        validate_external(mode, allow_external)
    except HTTPException:
        await image.close()
        raise
    await validate_image(image)
    fail(501, "extraction_not_implemented", "Foundation only: field extraction is not implemented.")
