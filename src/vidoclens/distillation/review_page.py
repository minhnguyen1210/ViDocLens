"""Render a private, blind human-review form; blank judgments stay blank."""

import argparse
import html
import json
import os
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.silver_review import SilverReviewPacket
from vidoclens.filtering.io import digest, read_model, write_text_exclusive
from vidoclens.student.data import safe_path


def render(packet_dir, image_root, image_map, output):
    packet = read_model(packet_dir / "packet.json", SilverReviewPacket)
    template = json.loads((packet_dir / "review_template.json").read_text(encoding="utf-8"))
    if template["packet_sha256"] != digest(packet):
        raise ValueError("review template belongs to another packet")
    mapping = json.loads(image_map.read_text(encoding="utf-8"))
    records = []
    for item in packet.items:
        source = safe_path(image_root.resolve(), mapping[item.sample.question.document_id])
        if sha256(source) != item.sample.image_sha256:
            raise ValueError("review image differs from sampled evidence")
        records.append(
            {
                "question": item.sample.question.question_raw,
                "answer": item.answer_raw,
                "image": Path(os.path.relpath(source, output.parent)).as_posix(),
                "ocr": "\n".join(s.text_raw for s in item.ocr.spans)
                if item.ocr
                else "OCR unavailable",
            }
        )
    data = json.dumps({"records": records, "review": template}, ensure_ascii=False).replace(
        "<", "\\u003c"
    )
    page = Path(__file__).with_name("review_template.html").read_text(encoding="utf-8")
    write_text_exclusive(output, page.replace("__DATA__", data))
    return {
        "items": len(records),
        "human_review_completed": False,
        "output": html.escape(str(output)),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("packet-dir", "image-root", "image-map", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    print(json.dumps(render(**vars(p.parse_args()))))


if __name__ == "__main__":
    main()
