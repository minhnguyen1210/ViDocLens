"""Single-GPU, answer-only QLoRA with deterministic sample order and real resume."""

import argparse
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.student.checkpoint import restore_rng, save_checkpoint, validate_checkpoint
from vidoclens.student.collator import StudentCollator
from vidoclens.student.data import epoch_order, load_plan, smoke_indices
from vidoclens.student.progress import write_progress
from vidoclens.student.runtime import generate, load_runtime, loss_step


def sample_schedule(rows, config, seed, kind):
    if kind == "smoke":
        subset = smoke_indices(rows)
        count = 52 * config.gradient_accumulation
        return [
            subset[i]
            for epoch in range(math.ceil(count / len(subset)))
            for i in epoch_order(len(subset), seed, epoch)
        ][:count]
    return [i for epoch in range(config.epochs) for i in epoch_order(len(rows), seed, epoch)]


def run(root, plan_dir, output, seed, kind="train", resume=None, stop_after=None):
    import torch
    from transformers import get_cosine_schedule_with_warmup

    root = root.resolve()
    plan_dir, output = root / plan_dir, root / output
    config, rows, _, manifest = load_plan(root, plan_dir)
    if kind == "train" and seed not in config.seeds:
        raise ValueError("primary training seed not registered")
    schedule = sample_schedule(rows, config, seed, kind)
    total = math.ceil(len(schedule) / config.gradient_accumulation)
    resumed = None
    if resume:
        resume = root / resume
        resumed = validate_checkpoint(resume, plan_dir)
        if (resumed["kind"], resumed["seed"], resumed["total_updates"]) != (kind, seed, total):
            raise ValueError("resume schedule/config mismatch")
    output.mkdir(parents=True, exist_ok=False)
    for source in Path(__file__).parent.glob("*.py"):
        (output / ("source_" + source.name)).write_bytes(source.read_bytes())
    write_json(output / "config.json", config.model_dump(mode="json"))
    model, processor, profile = load_runtime(
        root,
        config,
        training=True,
        seed=seed,
        adapter=resume / "adapter" if resume else None,
        processor_path=resume / "processor" if resume else None,
    )
    write_json(output / "profile.json", profile)
    collator = StudentCollator(
        root, processor, config, (plan_dir / "prompt.txt").read_text(encoding="utf-8")
    )
    parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(
        parameters, lr=config.learning_rate, weight_decay=config.weight_decay
    )
    scheduler = get_cosine_schedule_with_warmup(
        optimizer, math.ceil(total * config.warmup_ratio), total
    )
    begin = resumed["step"] if resumed else 0
    if resume:
        state = torch.load(resume / "training_state.pt", map_location="cpu", weights_only=True)
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        restore_rng(state["rng"])
    save_steps = {25, 50, 52} if kind == "smoke" else {math.ceil(total / 2), total}
    end = min(stop_after or total, total)
    if not begin < end:
        raise ValueError("no updates remain")
    metadata = {
        "kind": kind,
        "seed": seed,
        "plan_sha256": sha256(plan_dir / "manifest.json"),
        "base_revision": config.revision,
        "base_weights_sha256": config.weights_sha256,
        "config_sha256": sha256(plan_dir / "config.json"),
        "total_updates": total,
        "environment_lock_sha256": manifest["environment_lock_sha256"],
        "trainable_parameters": profile["trainable_parameters"],
        "target_modules": profile["target_modules"],
    }
    summary = metadata | {
        "complete": False,
        "started_at": datetime.now(UTC).isoformat(),
        "resumed_from": str(resume) if resume else None,
        "start_step": begin,
        "steps": [],
        "checkpoints": [],
        "error": None,
    }
    write_progress(output / "run.json", summary)
    try:
        for step in range(begin, end):
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            indices = schedule[
                step * config.gradient_accumulation : (step + 1) * config.gradient_accumulation
            ]
            optimizer.zero_grad(set_to_none=True)
            losses, lengths, targets, pixels = [], [], [], []
            for index in indices:
                row = rows[index]
                inputs = collator(row.input, row.answer_raw)
                lengths.append(inputs.input_ids.shape[1])
                targets.append(int((inputs.labels != -100).sum()))
                pixels.append(
                    int(inputs.image_grid_thw.prod()) * processor.image_processor.patch_size**2
                )
                loss = loss_step(model, inputs)
                if not torch.isfinite(loss).item():
                    raise RuntimeError("nonfinite training loss")
                losses.append(loss.detach().item())
                (loss / len(indices)).backward()
            norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True).item()
            if norm <= 0 or any(
                p.grad is not None for p in model.parameters() if not p.requires_grad
            ):
                raise RuntimeError("missing adapter gradients or frozen-base gradient leak")
            lr = scheduler.get_last_lr()[0]
            optimizer.step()
            scheduler.step()
            torch.cuda.synchronize()
            record = {
                "step": step + 1,
                "loss": sum(losses) / len(losses),
                "grad_norm": norm,
                "lr": lr,
                "examples": len(indices),
                "seconds": time.perf_counter() - start,
                "max_sequence_tokens": max(lengths),
                "max_target_tokens": max(targets),
                "max_image_pixels": max(pixels),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            }
            summary["steps"].append(record)
            with (output / "learning_curve.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
                stream.flush()
            print(json.dumps({"kind": kind, "seed": seed, **record}), flush=True)
            if step + 1 in save_steps or step + 1 == end:
                destination = output / f"checkpoint-{step + 1:04d}"
                save_checkpoint(
                    destination,
                    model,
                    processor,
                    optimizer,
                    scheduler,
                    metadata
                    | {
                        "step": step + 1,
                        "examples_seen": min(
                            (step + 1) * config.gradient_accumulation, len(schedule)
                        ),
                    },
                )
                summary["checkpoints"].append(
                    {
                        "path": destination.relative_to(root).as_posix(),
                        "sha256": sha256(destination / "checkpoint.json"),
                    }
                )
            summary["last_step"] = step + 1
            write_progress(output / "run.json", summary)
        # A fixed training-only probe enables actual adapter/processor reload comparison.
        model.eval()
        probe = rows[smoke_indices(rows)[0]].input
        raw, ids = generate(model, collator(probe), processor, config.max_new_tokens)
        write_json(
            output / "reload_probe.json",
            {"qid": probe.question.qid, "answer_raw": raw, "output_ids": ids},
        )
        summary["complete"] = end == total
    except Exception as error:
        summary["error"] = type(error).__name__
        raise
    finally:
        summary["finished_at"] = datetime.now(UTC).isoformat()
        summary["examples_total"] = len(schedule)
        summary["unique_training_examples"] = len(set(schedule))
        write_progress(output / "run.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--plan-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--kind", choices=["train", "smoke"], default="train")
    p.add_argument("--resume", type=Path)
    p.add_argument("--stop-after", type=int)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
