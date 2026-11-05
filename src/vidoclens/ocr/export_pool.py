"""Verify complete OCR coverage and export confidence proxies without reading gold."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from vidoclens.common.pilot import sha256
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import SilverPool
from vidoclens.filtering.io import digest, read_model, write_model, write_text_exclusive
from vidoclens.student.data import safe_path


def confidence_bin(result):
    if result.status != "ok" or not result.spans:
        return "ocr_missing_or_empty"
    scores = [s.engine_score for s in result.spans if s.engine_score is not None]
    if not scores:
        return "engine_confidence_unavailable"
    score = mean(scores)
    return (
        "engine_confidence_low"
        if score < 0.8
        else "engine_confidence_medium"
        if score < 0.95
        else "engine_confidence_high"
    )


def export(pool_path, ocr_dir, output):
    pool = read_model(pool_path, SilverPool)
    report = json.loads((ocr_dir / "summary.json").read_text(encoding="utf-8"))
    samples = {s.question.document_id: s for s in pool.samples}
    if report.get("status") != "pass" or report.get("images") != len(samples):
        raise ValueError("OCR run has not completed the full requested population")
    results = []
    for item in report["samples"]:
        path = safe_path(ocr_dir, item["ocr_file"])
        result = read_model(path, OCRResult)
        if sha256(path) != item["ocr_sha256"] or result.document_id != item["document_id"]:
            raise ValueError("OCR payload/sample checksum mismatch")
        if (
            result.document_id not in samples
            or result.image_sha256 != samples[result.document_id].image_sha256
        ):
            raise ValueError("OCR image outside requested pool")
        results.append(result)
    if len(results) != len(samples) or {r.document_id for r in results} != samples.keys():
        raise ValueError("OCR population is incomplete or duplicated")
    output.mkdir(parents=True, exist_ok=False)
    write_text_exclusive(output / "ocr.jsonl", "".join(r.model_dump_json() + "\n" for r in results))
    bins = {r.document_id: confidence_bin(r) for r in results}
    write_model(output / "quality_bins.json", bins)
    write_model(
        output / "manifest.json",
        {
            "complete": True,
            "pool_sha256": digest(pool),
            "source_summary_sha256": sha256(ocr_dir / "summary.json"),
            "images": len(results),
            "quality_bin_counts": dict(Counter(bins.values())),
            "quality_bin_basis": (
                "gold-independent engine mean confidence: "
                "<0.8, [0.8,0.95), >=0.95; missing separate"
            ),
            "human_ocr_quality_verified": False,
            "limitations": [
                "engine confidence is a diagnostic proxy, not semantic or character correctness"
            ],
            "files": {p.name: sha256(p) for p in output.glob("*.json*")},
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("pool-path", "ocr-dir", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    export(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
