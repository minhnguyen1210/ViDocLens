"""Validate every selected raw silver target using the unchanged student collator."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import percentile, sha256, write_json
from vidoclens.distillation.data import load_plan
from vidoclens.student.collator import StudentCollator


def run(root, plan_dir, output):
    from transformers import AutoProcessor

    root = root.resolve()
    plan_dir = root / plan_dir
    config, train, dev, _ = load_plan(root, plan_dir)
    processor = AutoProcessor.from_pretrained(
        root / "artifacts/models/Qwen3-VL-2B-Instruct" / config.revision,
        local_files_only=True,
        trust_remote_code=False,
    )
    processor.image_processor.size = {
        "shortest_edge": config.min_image_pixels,
        "longest_edge": config.max_image_pixels,
    }
    collator = StudentCollator(
        root, processor, config, (plan_dir / "prompt.txt").read_text(encoding="utf-8")
    )
    report = {
        "plan_sha256": sha256(plan_dir / "manifest.json"),
        "status": "pass",
        "populations": {},
    }
    for name, rows in (("train", train), ("dev", dev)):
        lengths, targets, images = [], [], []
        for i, row in enumerate(rows):
            inputs = collator(row.input, row.answer_raw) if name == "train" else collator(row)
            lengths.append(inputs.input_ids.shape[1])
            images.append(int(inputs.image_grid_thw.prod()) // 4)
            if name == "train":
                targets.append(int((inputs.labels != -100).sum()))
            if (i + 1) % 200 == 0:
                print(f"preflight {name} {i + 1}/{len(rows)}", flush=True)
        report["populations"][name] = {
            "n": len(rows),
            "max_sequence": max(lengths),
            "p95_sequence": percentile(lengths, 0.95),
            "max_image_tokens": max(images),
            "max_target_tokens": max(targets) if targets else None,
            "truncated": 0,
        }
    write_json(root / output, report)
    print(json.dumps(report), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--plan-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
