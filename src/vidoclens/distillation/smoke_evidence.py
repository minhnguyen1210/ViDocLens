"""Bind a successful GPU smoke proof to its unchanged preflight, runs and checkpoints."""

import json
import math

from vidoclens.common.pilot import sha256
from vidoclens.distillation.data import load_plan
from vidoclens.distillation.sampler import exposure_counts, schedule_digest
from vidoclens.distillation.train import sample_schedule
from vidoclens.student.checkpoint import validate_checkpoint
from vidoclens.student.data import safe_path


def verify(root, plans, campaign):
    plan = plans / "P1-full-17"
    config, rows, dev, manifest = load_plan(root, plan)
    plan_hash = sha256(plan / "manifest.json")
    proof = json.loads((campaign / "resume_proof.json").read_text(encoding="utf-8"))
    if (
        proof.get("status") != "pass"
        or proof["plan_sha256"] != plan_hash
        or proof["continuous_updates"] != 52
        or proof["resumed_updates"] != 2
        or any(
            proof.get(key) is not True
            for key in (
                "mixed_source_exposures_verified",
                "resume_greedy_tokens_equal",
                "fresh_process_reload_tokens_equal",
                "optimizer_scheduler_rng_restored",
            )
        )
    ):
        raise ValueError("actual mixed smoke/resume proof is incomplete")
    preflight = json.loads((campaign / "preflight.json").read_text(encoding="utf-8"))
    if preflight["status"] != "pass" or preflight["plan_sha256"] != plan_hash:
        raise ValueError("preflight belongs to another plan")
    for name, count in (("train", len(rows)), ("dev", len(dev))):
        population = preflight["populations"][name]
        if (
            population["n"] != count
            or population["truncated"] != 0
            or not 0 < population["max_sequence"] <= config.max_sequence_length
        ):
            raise ValueError("preflight does not cover the complete untruncated population")
    order = sample_schedule(rows, config, 17, "smoke")
    order_hash = schedule_digest(rows, order)
    if proof["schedule_sha256"] != order_hash:
        raise ValueError("smoke schedule changed after proof")
    for label, prefix, begin in (("smoke", "continuous", 0), ("smoke-resumed", "resumed", 50)):
        directory = campaign / label
        path = directory / "run.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        if (
            sha256(path) != proof[prefix + "_run_sha256"]
            or not run["complete"]
            or run["kind"] != "smoke"
            or run["seed"] != 17
            or run["start_step"] != begin
            or run["last_step"] != 52
            or run["plan_sha256"] != plan_hash
            or run["source_hashes"] != manifest["source_hashes"]
            or run["exposures"] != exposure_counts(rows, order)
            or run["schedule_sha256"] != order_hash
            or [r["step"] for r in run["steps"]] != list(range(begin + 1, 53))
            or [r["loss"] for r in run["steps"][-2:]] != proof[prefix + "_tail_losses"]
        ):
            raise ValueError("smoke trajectory differs from verified proof")
        for step in run["steps"]:
            if (
                any(
                    not math.isfinite(step[k]) or step[k] <= 0
                    for k in ("loss", "grad_norm", "seconds")
                )
                or not 0 < step["peak_reserved_bytes"] < 12 * 1024**3
            ):
                raise ValueError("smoke lacks finite loss/gradients and actual GPU measurements")
        expected_steps = {25, 50, 52} if begin == 0 else {52}
        actual_steps = set()
        for record in run["checkpoints"]:
            checkpoint = safe_path(root, record["path"])
            metadata = validate_checkpoint(checkpoint, plan)
            step = metadata["step"]
            if (
                checkpoint.parent != directory
                or sha256(checkpoint / "checkpoint.json") != record["sha256"]
                or metadata["schedule_sha256"] != order_hash
                or metadata["exposures"] != exposure_counts(rows, order[: step * 16])
            ):
                raise ValueError("smoke checkpoint evidence changed")
            actual_steps.add(step)
        if actual_steps != expected_steps:
            raise ValueError("required smoke/resume checkpoint missing")
    return proof
