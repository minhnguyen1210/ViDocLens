"""Verify real continuous versus resumed adapters and a fresh-process greedy reload."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.distillation.data import load_plan
from vidoclens.distillation.sampler import exposure_counts, schedule_digest
from vidoclens.distillation.train import sample_schedule
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.collator import StudentCollator
from vidoclens.student.data import smoke_indices
from vidoclens.student.runtime import generate, load_runtime


def run(root, plan_dir, continuous, resumed, output):
    import torch
    from safetensors.torch import load_file

    root = root.resolve()
    plan_dir, continuous, resumed = root / plan_dir, root / continuous, root / resumed
    config, rows, _, _ = load_plan(root, plan_dir)
    left = json.loads((continuous / "run.json").read_text(encoding="utf-8"))
    right = json.loads((resumed / "run.json").read_text(encoding="utf-8"))
    if (
        not left["complete"]
        or not right["complete"]
        or right["start_step"] != 50
        or left["last_step"] != 52
        or right["last_step"] != 52
    ):
        raise ValueError("required smoke/resume trajectories incomplete")
    order = sample_schedule(rows, config, left["seed"], "smoke")
    expected_counts = exposure_counts(rows, order)
    if any(
        r.get("exposures") != expected_counts
        or r.get("schedule_sha256") != schedule_digest(rows, order)
        for r in (left, right)
    ):
        raise ValueError("mixed sampler exposure/resume mismatch")
    checkpoints = [d / "checkpoint-0052" for d in (continuous, resumed)]
    for checkpoint in checkpoints:
        validate_checkpoint(checkpoint, plan_dir)
    a, b = [load_file(str(d / "adapter/adapter_model.safetensors")) for d in checkpoints]
    if a.keys() != b.keys():
        raise ValueError("adapter parameter keys differ")
    maximum = 0.0
    for key in a:
        torch.testing.assert_close(a[key], b[key], rtol=1e-4, atol=1e-5)
        maximum = max(maximum, float((a[key] - b[key]).abs().max()))
    continuous_probe = json.loads((continuous / "reload_probe.json").read_text(encoding="utf-8"))
    resumed_probe = json.loads((resumed / "reload_probe.json").read_text(encoding="utf-8"))
    if continuous_probe["output_ids"] != resumed_probe["output_ids"]:
        raise ValueError("resume changed greedy probe token IDs")
    model, processor, profile = load_runtime(
        root,
        config,
        adapter=checkpoints[1] / "adapter",
        processor_path=checkpoints[1] / "processor",
    )
    collator = StudentCollator(
        root, processor, config, (plan_dir / "prompt.txt").read_text(encoding="utf-8")
    )
    row = rows[smoke_indices(rows)[0]].input
    _, ids = generate(model, collator(row), processor, config.max_new_tokens)
    if ids != resumed_probe["output_ids"]:
        raise ValueError("fresh-process adapter/processor reload changed greedy output")
    state = torch.load(checkpoints[1] / "training_state.pt", map_location="cpu", weights_only=True)
    if (
        not {"optimizer", "scheduler", "rng"} <= state.keys()
        or not {"python", "numpy", "torch", "cuda"} <= state["rng"].keys()
    ):
        raise ValueError("missing resume states")
    report = {
        "status": "pass",
        "mixed_source_exposures_verified": True,
        "schedule_sha256": schedule_digest(rows, order),
        "plan_sha256": sha256(plan_dir / "manifest.json"),
        "continuous_run_sha256": sha256(continuous / "run.json"),
        "resumed_run_sha256": sha256(resumed / "run.json"),
        "continuous_updates": len(left["steps"]),
        "resumed_updates": len(right["steps"]),
        "adapter_tensor_rtol": 1e-4,
        "adapter_tensor_atol": 1e-5,
        "max_adapter_absolute_difference": maximum,
        "resume_greedy_tokens_equal": True,
        "fresh_process_reload_tokens_equal": True,
        "optimizer_scheduler_rng_restored": True,
        "reload_profile": profile,
        "continuous_tail_losses": [r["loss"] for r in left["steps"][-2:]],
        "resumed_tail_losses": [r["loss"] for r in right["steps"]],
    }
    write_json(root / output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "reload_profile"}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ["plan-dir", "continuous", "resumed", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
