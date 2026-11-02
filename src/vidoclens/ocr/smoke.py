"""CPU PaddleOCR feasibility pilot with pinned local weights and no remote processing."""

import argparse
import hashlib
import inspect
import json
import time
import unicodedata
from pathlib import Path

from vidoclens.common.pilot import (
    checked_image,
    environment,
    load_pilot,
    percentile,
    sha256,
    snapshot_sources,
    write_json,
)
from vidoclens.contracts.models import Box, OCRResult, OCRSpan


def verify_model(path: Path) -> dict:
    manifest = json.loads((path / "download_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        file = (path / item["file"]).resolve()
        if not file.is_relative_to(path.resolve()) or sha256(file) != item["sha256"]:
            raise ValueError("OCR model manifest/hash mismatch")
    return manifest


def run(args: argparse.Namespace) -> None:
    import numpy as np
    import paddle
    import psutil
    from paddleocr import PaddleOCR
    from PIL import Image, ImageDraw, ImageOps

    data = load_pilot(args.root, args.manifest, args.image_inventory)
    detector = verify_model(args.detector)
    recognizer = verify_model(args.recognizer)
    assert paddle.__version__ == "3.2.0"
    paddle.set_device("cpu")
    assert paddle.get_device() == "cpu"
    mapping = PaddleOCR._get_ocr_model_names(None, "vi", "PP-OCRv5")
    assert mapping == ("PP-OCRv5_server_det", "latin_PP-OCRv5_mobile_rec"), mapping
    assert detector["model_id"] == "PaddlePaddle/" + mapping[0]
    assert recognizer["model_id"] == "PaddlePaddle/" + mapping[1]
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot_sources(args.output, Path(__file__))
    write_json(args.output / "environment.json", environment())
    write_json(args.output / "pilot_manifest.json", data.model_dump())
    settings = {
        "text_detection_model_name": mapping[0],
        "text_detection_model_dir": str(args.detector),
        "text_recognition_model_name": mapping[1],
        "text_recognition_model_dir": str(args.recognizer),
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "device": "cpu",
        "cpu_threads": 4,
        "enable_mkldnn": False,
        "text_det_limit_side_len": 960,
        "text_det_limit_type": "max",
        "text_recognition_batch_size": 6,
    }
    preprocess = {
        "transform": "EXIF transpose, RGB to BGR",
        "det_limit_side_len": 960,
        "det_limit_type": "max",
        "orientation": False,
        "unwarping": False,
    }
    preprocessing_hash = hashlib.sha256(json.dumps(preprocess, sort_keys=True).encode()).hexdigest()
    engine_revision = f"paddleocr-3.2.0:{detector['revision']}:{recognizer['revision']}"
    start = time.perf_counter()
    engine = PaddleOCR(**settings)
    profile = {
        "settings": settings,
        "language_mapping": list(mapping),
        "language": "vi",
        "language_mapping_source_sha256": hashlib.sha256(
            inspect.getsource(PaddleOCR._get_ocr_model_names).encode()
        ).hexdigest(),
        "detector": detector,
        "recognizer": recognizer,
        "cold_load_seconds": time.perf_counter() - start,
        "runner_sha256": sha256(Path(__file__)),
        "manifest_sha256": sha256(args.manifest),
        "preprocessing": preprocess,
        "preprocessing_hash": preprocessing_hash,
        "cer_evaluated": False,
        "quality_pilot_100_images_complete": False,
    }
    write_json(args.output / "profile.json", profile)

    def predict(row, index=None):
        start = time.perf_counter()
        with Image.open(checked_image(args.root, row)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
        if image.size != (row.width, row.height):
            raise ValueError("image dimensions changed; coordinate transform not supported")
        raw = list(engine.predict(np.asarray(image)[:, :, ::-1].copy()))
        if len(raw) != 1:
            raise ValueError("one OCR result per receipt required")
        obj = raw[0].json
        obj = json.loads(obj) if isinstance(obj, str) else obj
        result = obj.get("res", obj)
        texts, scores, polygons = result["rec_texts"], result["rec_scores"], result["rec_polys"]
        if not (len(texts) == len(scores) == len(polygons)):
            raise ValueError("OCR text/box/score counts differ")
        spans = []
        draw = ImageDraw.Draw(image)
        for i, (text, score, polygon) in enumerate(zip(texts, scores, polygons, strict=True)):
            x, y = zip(*polygon, strict=True)
            left, top = max(0, min(x)), max(0, min(y))
            right, bottom = min(row.width, max(x)), min(row.height, max(y))
            box = Box(
                x0=left / row.width,
                y0=top / row.height,
                x1=right / row.width,
                y1=bottom / row.height,
            )
            spans.append(
                OCRSpan(
                    span_id=f"line-{i}",
                    text_raw=text,
                    text_nfc=unicodedata.normalize("NFC", text),
                    box=box,
                    line_id=f"line-{i}",
                    reading_order=i,
                    engine_score=score,
                )
            )
            draw.rectangle(
                (left, top, right, bottom), outline="red", width=max(1, row.width // 500)
            )
        canonical = OCRResult(
            document_id=row.document_id,
            engine="paddleocr",
            engine_revision=engine_revision,
            preprocessing_hash=preprocessing_hash,
            image_sha256=row.image_sha256,
            status="ok" if spans else "empty",
            spans=spans,
        )
        report = {
            "document_id": row.document_id,
            "status": canonical.status,
            "spans": len(spans),
            "total_seconds": time.perf_counter() - start,
            "rss_bytes": psutil.Process().memory_info().rss,
        }
        if index is not None:
            write_json(args.output / f"ocr_{index:02d}.json", canonical.model_dump())
            write_json(args.output / f"raw_{index:02d}.json", obj)
            image.save(args.output / f"boxes_{index:02d}.jpg")
        return report

    write_json(args.output / "warmup.json", predict(data.pilot[0]))
    results = []
    for i, row in enumerate(data.pilot):
        try:
            result = predict(row, i)
        except Exception as error:
            result = {
                "document_id": row.document_id,
                "status": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        results.append(result)
        write_json(args.output / f"sample_{i:02d}.json", result)
        print(f"ocr {i + 1}/{len(data.pilot)}: {result['status']}", flush=True)
    ok = [r for r in results if r["status"] == "ok"]
    summary = {
        "status": "pass" if len(ok) == len(results) else "fail",
        "samples": len(results),
        "nonempty_receipts": len(ok),
        "total_spans": sum(r.get("spans", 0) for r in results),
        "warmup_excluded": True,
        "device": paddle.get_device(),
        "cer_evaluated": False,
        "visual_review_complete": False,
    }
    if ok:
        summary.update(
            {
                "p50_seconds": percentile([r["total_seconds"] for r in ok], 0.5),
                "p95_seconds": percentile([r["total_seconds"] for r in ok], 0.95),
                "peak_sampled_rss_bytes": max(r["rss_bytes"] for r in ok),
            }
        )
    write_json(args.output / "ocr_smoke.json", summary)
    print(json.dumps(summary), flush=True)
    if summary["status"] != "pass":
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "manifest", "image-inventory", "detector", "recognizer", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
