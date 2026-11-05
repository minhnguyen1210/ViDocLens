"""Question-only local inference; no dev gold is loaded by this module."""

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.distillation import DistillationPlan
from vidoclens.filtering.io import read_model
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.collator import StudentCollator
from vidoclens.student.data import safe_path
from vidoclens.student.predict import load_inputs
from vidoclens.student.runtime import generate, load_runtime


def run(root, plan_dir, output, checkpoint=None):
    import torch

    root = root.resolve()
    plan_dir, output = root / plan_dir, root / output
    config, rows = load_inputs(root, plan_dir)
    manifest = read_model(plan_dir / "manifest.json", DistillationPlan)
    for name, checksum in manifest.source_hashes.items():
        if sha256(safe_path(root, name)) != checksum:
            raise ValueError("distillation inference source changed")
    if checkpoint is None:
        raise ValueError("Phase 4 inference requires a trained adapter")
    if checkpoint:
        checkpoint = root / checkpoint
        meta = validate_checkpoint(checkpoint, plan_dir)
        if meta["kind"] != "train":
            raise ValueError("smoke adapter is not a baseline")
    output.mkdir(parents=True, exist_ok=False)
    model, processor, profile = load_runtime(
        root,
        config,
        adapter=checkpoint / "adapter" if checkpoint else None,
        processor_path=checkpoint / "processor" if checkpoint else None,
    )
    write_json(output / "profile.json", profile)
    collator = StudentCollator(
        root, processor, config, (plan_dir / "prompt.txt").read_text(encoding="utf-8")
    )
    summary = {
        "complete": False,
        "kind": manifest.arm,
        "checkpoint": str(checkpoint) if checkpoint else None,
        "checkpoint_sha256": sha256(checkpoint / "checkpoint.json") if checkpoint else None,
        "plan_sha256": sha256(plan_dir / "manifest.json"),
        "expected": len(rows),
        "started_at": datetime.now(UTC).isoformat(),
        "status_counts": {},
        "completed": 0,
        "gold_in_input": False,
        "error": None,
        "profile_sha256": sha256(output / "profile.json"),
        "source_hashes": manifest.source_hashes,
    }
    counts = Counter()
    try:
        with (output / "predictions.jsonl").open("x", encoding="utf-8") as stream:
            for i, row in enumerate(rows):
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                started = time.perf_counter()
                inputs = collator(row)
                raw, ids = generate(model, inputs, processor, config.max_new_tokens)
                torch.cuda.synchronize()
                status = "answered" if raw.strip() else "abstained"
                result = {
                    "qid": row.question.qid,
                    "document_id": row.question.document_id,
                    "status": status,
                    "answer_raw": raw if status == "answered" else None,
                    "output_ids": ids,
                    "output_tokens": len(ids),
                    "input_tokens": inputs.input_ids.shape[1],
                    "image_tokens": int(inputs.image_grid_thw.prod()) // 4,
                    "hit_output_limit": len(ids) >= config.max_new_tokens
                    and ids[-1] != collator.eos_id,
                    "seconds": time.perf_counter() - started,
                    "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                    "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                }
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                stream.flush()
                counts[status] += 1
                summary["completed"] = i + 1
                if (i + 1) % 25 == 0:
                    print(f"{summary['kind']} inference {i + 1}/{len(rows)}", flush=True)
            summary["complete"] = True
    except Exception as error:
        summary["error"] = type(error).__name__
        raise
    finally:
        summary["finished_at"] = datetime.now(UTC).isoformat()
        summary["status_counts"] = dict(counts)
        if (output / "predictions.jsonl").exists():
            summary["predictions_sha256"] = sha256(output / "predictions.jsonl")
        write_json(output / "run.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--plan-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
