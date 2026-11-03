"""Question-only local inference; no dev gold is loaded by this module."""

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.student import StudentConfig, StudentQuestion
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.collator import StudentCollator
from vidoclens.student.data import safe_path
from vidoclens.student.runtime import generate, load_runtime


def load_inputs(root, plan_dir):
    from vidoclens.data.freeze import load_frozen_plan
    from vidoclens.data.receiptvqa import load_questions

    manifest = json.loads((plan_dir / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        if sha256(safe_path(plan_dir, name)) != digest:
            raise ValueError("student inference plan checksum mismatch")
    split_dir = root / "data/splits/receiptvqa_containment_v1"
    plan = load_frozen_plan(split_dir, 10)
    if sha256(split_dir / "summary.json") != manifest["split_sha256"]:
        raise ValueError("inference split changed")
    config = StudentConfig.model_validate_json((plan_dir / "config.json").read_text())
    rows = [
        StudentQuestion.model_validate_json(s)
        for s in (plan_dir / "dev.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assignments = {a.source_image_id: a for a in plan.assignments}
    questions = {
        q.qid: q
        for q in load_questions(
            root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", split="dev"
        )
    }
    for row in rows:
        a = assignments[row.question.source_image_id]
        if (
            row.partition != "dev_select"
            or (a.partition, a.duplicate_group_id) != (row.partition, row.duplicate_group_id)
            or questions.get(row.question.qid) != row.question
        ):
            raise ValueError("inference input not authorized dev question")
    if len(rows) != manifest["dev_qa"] or len({r.question.qid for r in rows}) != len(rows):
        raise ValueError("inference population mismatch")
    return config, rows


def run(root, plan_dir, output, checkpoint=None):
    import torch

    root = root.resolve()
    plan_dir, output = root / plan_dir, root / output
    config, rows = load_inputs(root, plan_dir)
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
        "kind": "L2" if checkpoint else "L1",
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
        "source_hashes": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
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
