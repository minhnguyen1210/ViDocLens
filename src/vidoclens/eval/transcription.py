"""Score explicitly reviewed OCR lines, keeping AI and human evidence separate."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.review import TranscriptionReview
from vidoclens.eval.oracle import character_error_rate


def evaluate_reviews(review_files: list[Path], ocr_dir: Path) -> dict:
    pairs = defaultdict(list)
    skipped = missing = 0
    documents = set()
    for file in review_files:
        review = TranscriptionReview.model_validate_json(file.read_text(encoding="utf-8"))
        if review.document_id in documents:
            raise ValueError("duplicate reviewed document")
        documents.add(review.document_id)
        image_id = int(review.document_id.rsplit(":", 1)[-1])
        ocr_file = ocr_dir / f"ocr_{image_id}.json"
        image_file = ocr_dir / "images" / f"{image_id}.jpg"
        if sha256(ocr_file) != review.ocr_sha256 or sha256(image_file) != review.image_sha256:
            raise ValueError("review provenance checksum mismatch")
        result = OCRResult.model_validate_json(ocr_file.read_text(encoding="utf-8"))
        if result.document_id != review.document_id:
            raise ValueError("OCR/review document mismatch")
        lines = {s.span_id: s.text_raw for s in result.spans}
        for line in review.lines:
            if line.legibility == "uncertain":
                skipped += 1
                continue
            if line.line_id.startswith("missing-"):
                predicted = ""
                missing += 1
            else:
                if line.line_id not in lines:
                    raise ValueError("review points to nonexistent OCR line")
                predicted = lines[line.line_id]
            pairs[review.reviewer_type].append((predicted, line.reference))
    return {
        "documents": len(documents),
        "uncertain_lines_excluded": skipped,
        "missing_detections_included_as_deletions": missing,
        "by_reviewer_type": {
            key: {"lines": len(values), **character_error_rate(values)}
            for key, values in pairs.items()
        },
        "human_review_available": bool(pairs.get("human")),
        "limitations": [
            "selected readable lines, not representative corpus CER",
            "AI references can be wrong; not human gold",
            "selected missing lines count as deletions; not full-image detection recall",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.reviews.glob("review_*.json"))
    if not files:
        raise ValueError("no review records")
    report = evaluate_reviews(files, args.ocr_dir)
    write_json(args.output, report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
