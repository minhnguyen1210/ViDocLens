"""Immutable filter bundles with checked files and deterministic decision replay."""

import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import FilterRun, SilverBatch, SilverPool
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.pipeline import filter_batch, summarize

FILES = {"pool.json", "batch.json", "ocr.json", "run.json", "summary.json"}


def write_bundle(output, pool, batch, ocr, config):
    run = filter_batch(pool, batch, ocr, config)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("pool.json", pool),
        ("batch.json", batch),
        ("run.json", run),
        ("ocr.json", [r.model_dump(mode="json") for r in ocr]),
        ("summary.json", summarize(run)),
    ):
        write_model(output / name, value)
    write_model(
        output / "manifest.json",
        {
            "protocol": "silver_filter_bundle_v1",
            "complete": True,
            "files": {name: sha256(output / name) for name in sorted(FILES)},
        },
    )
    return run


def load_bundle(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("protocol") != "silver_filter_bundle_v1"
        or manifest.get("complete") is not True
        or set(manifest.get("files", {})) != FILES
    ):
        raise ValueError("incomplete/invalid filter bundle manifest")
    for name, expected in manifest["files"].items():
        if sha256(directory / name) != expected:
            raise ValueError("filter bundle checksum mismatch")
    pool = read_model(directory / "pool.json", SilverPool)
    batch = read_model(directory / "batch.json", SilverBatch)
    run = read_model(directory / "run.json", FilterRun)
    ocr = [
        OCRResult.model_validate(r)
        for r in json.loads((directory / "ocr.json").read_text(encoding="utf-8"))
    ]
    replay = filter_batch(pool, batch, ocr, run.config)
    if digest(replay) != digest(run):
        raise ValueError("filter replay differs; inputs/code changed, create a new run")
    if json.loads((directory / "summary.json").read_text(encoding="utf-8")) != summarize(run):
        raise ValueError("filter summary mismatch")
    return pool, batch, run
