"""Run 100 actual local OCR receipts from frozen G10 train, with a reusable cache."""

import argparse
import hashlib
import html
import json
import os
import time
import unicodedata
import zipfile
from pathlib import Path

from vidoclens.common.pilot import environment, percentile, sha256, write_json
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.models import Box, OCRResult, OCRSpan
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.images import canonical_image, pixel_sha256
from vidoclens.ocr.cache import cache_key, load_cache, store_cache
from vidoclens.ocr.smoke import verify_model


def select_pilot(images, plan, count=100):
    inventory = {r.source_image_id: r for r in images}
    selected = {}
    for row in sorted(plan.assignments, key=lambda r: r.source_image_id):
        if row.partition == "train_fit" and row.gold_for_training:
            selected.setdefault(row.duplicate_group_id, inventory[row.source_image_id])
    ranked = sorted(
        selected, key=lambda g: hashlib.sha256(("42:ocr-quality:" + g).encode()).hexdigest()
    )
    if len(ranked) < count:
        raise ValueError("not enough distinct G10 train components for requested OCR pilot")
    return [selected[g] for g in ranked[:count]]


def render_review(output: Path, items):
    rows = []
    for item in items:
        image_id = item["source_image_id"]
        result = OCRResult.model_validate_json(
            (output / item["ocr_file"]).read_text(encoding="utf-8")
        )
        content = "\n".join(f"{s.span_id}: {s.text_raw}" for s in result.spans)
        rows.append(
            f'<article id="image-{image_id}"><h2>Receipt {image_id}</h2>'
            f'<img loading="lazy" src="images/{image_id}.jpg" alt="receipt {image_id}">'
            "<p>Transcribe from the image before opening OCR; "
            "never infer unreadable characters.</p>"
            "<details><summary>OCR output (may be wrong)</summary>"
            f"<pre>{html.escape(content)}</pre></details></article>"
        )
    page = (
        '<!doctype html><meta charset="utf-8"><title>Local OCR review</title>'
        "<style>body{font:16px sans-serif;max-width:1100px;margin:auto}"
        "article{border-bottom:2px solid #aaa;padding:24px}"
        "img{max-width:100%;max-height:1600px}pre{white-space:pre-wrap}</style>"
        "<h1>OCR review — private local images</h1>" + "\n".join(rows)
    )
    (output / "review.html").write_text(page, encoding="utf-8")


def run(root: Path, split_dir: Path, inventory_dir: Path, archive: Path, output: Path):
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    import numpy as np
    import paddle
    import psutil
    from paddleocr import PaddleOCR
    from PIL import ImageDraw

    plan = load_frozen_plan(split_dir, 10)
    inventory_file = inventory_dir / "images.jsonl"
    if sha256(inventory_file) != plan.image_inventory_sha256:
        raise ValueError("OCR inventory does not match frozen split")
    images = [
        CorpusImage.model_validate_json(line) for line in inventory_file.read_text().splitlines()
    ]
    selected = select_pilot(images, plan)
    if {r.image_archive_sha256 for r in selected} != {sha256(archive)}:
        raise ValueError("image archive changed")
    models = root / "artifacts/models/paddleocr"
    det = models / "PP-OCRv5_server_det/ca867c897ecbca8873081573a802ad70d499cb94"
    rec = models / "latin_PP-OCRv5_mobile_rec/ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57"
    detector, recognizer = verify_model(det), verify_model(rec)
    lock = root / "infra/requirements/phase0-ocr-linux-py311.lock"
    settings = {
        "text_detection_model_name": "PP-OCRv5_server_det",
        "text_detection_model_dir": str(det),
        "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
        "text_recognition_model_dir": str(rec),
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
    preprocessing = {k: v for k, v in settings.items() if not k.endswith("_dir")}
    preprocessing["transform"] = "canonical EXIF RGB, BGR for Paddle; engine reading order"
    ph = hashlib.sha256(json.dumps(preprocessing, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    (output / "images").mkdir()
    write_json(output / "environment.json", environment())
    (output / "source_quality.py").write_bytes(Path(__file__).read_bytes())
    (output / "source_cache.py").write_bytes(Path(__file__).with_name("cache.py").read_bytes())
    write_json(
        output / "selection.json",
        {
            "policy": "100 distinct frozen G10 train_fit components, seed42",
            "split_summary_sha256": sha256(split_dir / "summary.json"),
            "gold_budget": 10,
            "images": [r.model_dump() for r in selected],
        },
    )
    start = time.perf_counter()
    paddle.set_device("cpu")
    engine = PaddleOCR(**settings)
    profile = {
        "settings": settings,
        "preprocessing_hash": ph,
        "language": "vi",
        "cold_load_seconds": time.perf_counter() - start,
        "detector": detector,
        "recognizer": recognizer,
        "package_lock_sha256": sha256(lock),
        "human_quality_verified": False,
        "split_directory": str(split_dir),
    }
    write_json(output / "profile.json", profile)
    results = []
    cache_dir = root / "data/ocr_cache/phase1"
    with zipfile.ZipFile(archive) as source:
        for i, row in enumerate(selected):
            start = time.perf_counter()
            payload = source.read(row.archive_member)
            if hashlib.sha256(payload).hexdigest() != row.raw_image_sha256:
                raise ValueError("selected image hash mismatch")
            image, _ = canonical_image(payload)
            if pixel_sha256(image) != row.canonical_pixel_sha256:
                raise ValueError("canonical transform drift")
            (output / "images" / f"{row.source_image_id}.jpg").write_bytes(payload)
            identity = {
                "document_id": row.document_id,
                "raw_image_sha256": row.raw_image_sha256,
                "canonical_pixel_sha256": row.canonical_pixel_sha256,
                "preprocessing": preprocessing,
                "language": "vi",
                "engine": "paddleocr-3.2.0/paddle-3.2.0",
                "detector": {
                    "revision": detector["revision"],
                    "manifest_sha256": sha256(det / "download_manifest.json"),
                },
                "recognizer": {
                    "revision": recognizer["revision"],
                    "manifest_sha256": sha256(rec / "download_manifest.json"),
                },
                "package_lock_sha256": sha256(lock),
            }
            result = load_cache(cache_dir, identity)
            hit = result is not None
            inference_seconds = None
            if result is None:
                t = time.perf_counter()
                raw = list(engine.predict(np.asarray(image)[:, :, ::-1].copy()))
                inference_seconds = time.perf_counter() - t
                if len(raw) != 1:
                    raise ValueError("expected one OCR result")
                obj = raw[0].json
                obj = json.loads(obj) if isinstance(obj, str) else obj
                obj = obj.get("res", obj)
                spans = []
                for j, (text, confidence, polygon) in enumerate(
                    zip(obj["rec_texts"], obj["rec_scores"], obj["rec_polys"], strict=True)
                ):
                    xs, ys = zip(*polygon, strict=True)
                    box = Box(
                        x0=max(0, min(xs)) / image.width,
                        y0=max(0, min(ys)) / image.height,
                        x1=min(image.width, max(xs)) / image.width,
                        y1=min(image.height, max(ys)) / image.height,
                    )
                    spans.append(
                        OCRSpan(
                            span_id=f"line-{j}",
                            line_id=f"line-{j}",
                            reading_order=j,
                            text_raw=text,
                            text_nfc=unicodedata.normalize("NFC", text),
                            box=box,
                            engine_score=confidence,
                        )
                    )
                result = OCRResult(
                    document_id=row.document_id,
                    image_sha256=row.raw_image_sha256,
                    engine="paddleocr",
                    engine_revision=f"3.2.0:{detector['revision']}:{recognizer['revision']}",
                    preprocessing_hash=ph,
                    status="ok" if spans else "empty",
                    spans=spans,
                )
                store_cache(cache_dir, identity, result)
            assert load_cache(cache_dir, identity) == result
            name = f"ocr_{row.source_image_id}.json"
            write_json(output / name, result.model_dump())
            draw = ImageDraw.Draw(image)
            for span in result.spans:
                b = span.box
                draw.rectangle(
                    (
                        b.x0 * image.width,
                        b.y0 * image.height,
                        b.x1 * image.width,
                        b.y1 * image.height,
                    ),
                    outline="red",
                    width=2,
                )
            image.thumbnail((700, 1400))
            image.save(output / f"boxes_{row.source_image_id}.jpg")
            item = {
                "source_image_id": row.source_image_id,
                "document_id": row.document_id,
                "ocr_file": name,
                "ocr_sha256": sha256(output / name),
                "status": result.status,
                "spans": len(result.spans),
                "cache_key": cache_key(identity),
                "cache_hit": hit,
                "inference_seconds": inference_seconds,
                "total_seconds": time.perf_counter() - start,
                "rss_bytes": psutil.Process().memory_info().rss,
            }
            write_json(output / f"sample_{row.source_image_id}.json", item)
            results.append(item)
            print(f"OCR {i + 1}/100 {result.status}", flush=True)
    render_review(output, results)
    times = [r["inference_seconds"] for r in results if r["inference_seconds"] is not None]
    report = {
        "status": "pass",
        "images": len(results),
        "spans": sum(r["spans"] for r in results),
        "cache_hits": sum(r["cache_hit"] for r in results),
        "empty_images": sum(r["status"] == "empty" for r in results),
        "p50_inference_seconds": percentile(times, 0.5) if times else None,
        "p95_inference_seconds": percentile(times, 0.95) if times else None,
        "first_inference_included": True,
        "deployment_latency_benchmark": False,
        "peak_sampled_rss_bytes": max(r["rss_bytes"] for r in results),
        "human_review_complete": False,
        "samples": results,
    }
    write_json(output / "summary.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "samples"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "split-dir", "inventory-dir", "archive", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
