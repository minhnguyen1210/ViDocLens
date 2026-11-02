"""Bounded image decoding and versioned fingerprints. Raw bytes are never modified."""

import hashlib
import io
import json
import struct
import warnings

from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 64 * 1024**2
MAX_PIXELS = 50_000_000
TRANSFORM = {
    "version": "receipt_rgb_v1",
    "operations": ["EXIF transpose", "convert RGB", "discard metadata"],
    "pixel_hash": "sha256(version prefix + big-endian width/height + RGB bytes)",
    "fingerprint": "32x32 LANCZOS grayscale, unnormalized separable DCT-II, 8x8 median bits",
    "center_crop_fraction": 0.8,
}
TRANSFORM_HASH = hashlib.sha256(json.dumps(TRANSFORM, sort_keys=True).encode()).hexdigest()


def canonical_image(payload: bytes) -> tuple[Image.Image, dict]:
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("image payload missing or exceeds byte limit")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(payload)) as source:
            if source.format not in {"JPEG", "PNG"} or getattr(source, "n_frames", 1) != 1:
                raise ValueError("only single-frame JPEG/PNG is permitted")
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("offline image pixel limit exceeded")
            metadata = {
                "raw_width": source.width,
                "raw_height": source.height,
                "source_format": source.format,
                "source_mode": source.mode,
                "exif_orientation": source.getexif().get(274),
            }
            source.load()  # Full decode, not just header verification.
            rgb = ImageOps.exif_transpose(source).convert("RGB")
            canonical = Image.new("RGB", rgb.size)
            canonical.paste(rgb)
            canonical.info.clear()
    return canonical, metadata


def pixel_sha256(image: Image.Image) -> str:
    if image.mode != "RGB":
        raise ValueError("pixel hashes require canonical RGB")
    digest = hashlib.sha256(b"vidoclens:rgb-pixels:v1\0")
    digest.update(struct.pack(">II", *image.size))
    digest.update(image.tobytes())
    return digest.hexdigest()


def phash64(image: Image.Image) -> str:
    # NumPy is a data extra; core/label loaders do not import it.
    import numpy as np

    grid = np.asarray(
        image.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64
    )
    positions = np.arange(32, dtype=np.float64) + 0.5
    frequencies = np.arange(8, dtype=np.float64)[:, None]
    basis = np.cos(np.pi * frequencies * positions / 32)
    low_frequencies = basis @ grid @ basis.T
    bits = low_frequencies > np.median(low_frequencies)
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def fingerprints(payload: bytes) -> dict:
    image, metadata = canonical_image(payload)
    width, height = image.size
    margin_x, margin_y = width // 10, height // 10
    cropped = image.crop((margin_x, margin_y, width - margin_x, height - margin_y))
    return {
        **metadata,
        "width": width,
        "height": height,
        "raw_image_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_bytes": len(payload),
        "canonical_pixel_sha256": pixel_sha256(image),
        "transform_sha256": TRANSFORM_HASH,
        "phash64": phash64(image),
        "center_crop_phash64": phash64(cropped),
    }
