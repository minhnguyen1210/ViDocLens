"""Run the preregistered local L1/L2 campaign in separate, sequential GPU processes."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.student.data import load_plan
from vidoclens.student.progress import write_progress


def run(root, plan_dir, output, preflight, resume_proof, protocol):
    root = root.resolve()
    config, _, _, _ = load_plan(root, root / plan_dir)
    plan_hash = sha256(root / plan_dir / "manifest.json")
    for path in (preflight, resume_proof):
        evidence = json.loads((root / path).read_text())
        if evidence["status"] != "pass" or evidence["plan_sha256"] != plan_hash:
            raise ValueError("processor/resume gate not passed for this plan")
    protocol_data = json.loads((root / protocol).read_text())
    if protocol_data["plan_sha256"] != plan_hash:
        raise ValueError("dev protocol belongs to another plan")
    directory = root / output
    directory.mkdir(parents=True, exist_ok=False)
    state = {
        "complete": False,
        "plan_sha256": plan_hash,
        "steps": [],
        "preflight_sha256": sha256(root / preflight),
        "resume_proof_sha256": sha256(root / resume_proof),
        "protocol_sha256": sha256(root / protocol),
        "error": None,
        "preflight": preflight.as_posix(),
        "resume_proof": resume_proof.as_posix(),
        "protocol": protocol.as_posix(),
        "output": output.as_posix(),
    }
    write_progress(directory / "campaign.json", state)

    def execute(module, arguments):
        command = [sys.executable, "-m", module, *map(str, arguments)]
        label = module + " " + " ".join(map(str, arguments))
        print("START " + label, flush=True)
        entry = {"command": ["python", "-m", module, *map(str, arguments)], "exit_code": None}
        state["steps"].append(entry)
        write_progress(directory / "campaign.json", state)
        log_path = directory / f"step_{len(state['steps']):02d}.log"
        with log_path.open("x", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            exit_code = process.wait()
        entry.update({"exit_code": exit_code, "log": log_path.name, "log_sha256": sha256(log_path)})
        write_progress(directory / "campaign.json", state)
        if exit_code:
            raise RuntimeError("campaign step failed; inspect private local log")

    def evaluate(checkpoint, label):
        destination = output / label
        args = ["--plan-dir", plan_dir, "--output", destination]
        if checkpoint:
            args += ["--checkpoint", checkpoint]
        execute("vidoclens.student.predict", args)
        execute(
            "vidoclens.eval.student",
            [
                "evaluate",
                "--plan-dir",
                plan_dir,
                "--run-dir",
                destination,
                "--protocol-path",
                protocol,
                "--output",
                destination / "metrics.json",
            ],
        )

    try:
        evaluate(None, "L1")
        for seed in config.seeds:
            train_dir = output / f"L2_seed{seed}"
            execute(
                "vidoclens.student.train",
                ["--plan-dir", plan_dir, "--output", train_dir, "--seed", seed],
            )
            training = json.loads((root / train_dir / "run.json").read_text())
            if not training["complete"]:
                raise RuntimeError("training did not complete full preregistered budget")
            for cp in training["checkpoints"]:
                checkpoint = Path(cp["path"])
                step = int(checkpoint.name.split("-")[-1])
                evaluate(checkpoint, f"L2_seed{seed}_step{step}")
        state["complete"] = True
    except Exception as error:
        state["error"] = type(error).__name__
        raise
    finally:
        write_progress(directory / "campaign.json", state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ["plan-dir", "output", "preflight", "resume-proof", "protocol"]:
        p.add_argument("--" + name, type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
