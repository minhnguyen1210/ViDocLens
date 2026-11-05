"""Sequential mixed-source smoke, real resume verification, and nine training arms."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.distillation.data import load_plan
from vidoclens.student.progress import write_progress


def run(root, plans, output):
    root = root.resolve()
    plans, output = root / plans, root / output
    for arm in ("P1-full", "P1-size", "P2"):
        for seed in (17, 42, 2026):
            load_plan(root, plans / f"{arm}-{seed}")
    output.mkdir(parents=True, exist_ok=False)
    state = {
        "complete": False,
        "steps": [],
        "error": None,
        "plans_manifest_sha256": sha256(plans / "manifest.json"),
    }

    def execute(module, arguments):
        command = [sys.executable, "-u", "-m", module, *map(str, arguments)]
        entry = {"command": ["python", *command[1:]], "exit_code": None}
        state["steps"].append(entry)
        log_path = output / f"step-{len(state['steps']):02d}.log"
        write_progress(output / "campaign.json", state)
        process = None
        try:
            with log_path.open("x", encoding="utf-8") as log:
                process = subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                code = process.wait()
            entry.update(exit_code=code, log=log_path.name, log_sha256=sha256(log_path))
            if code:
                raise RuntimeError("Phase 4 campaign step failed; inspect recorded private log")
        except BaseException:
            if process is not None and process.poll() is None:
                import signal

                process.send_signal(signal.SIGINT)
                entry["exit_code"] = process.wait()
            raise
        finally:
            if log_path.exists():
                entry.update(log=log_path.name, log_sha256=sha256(log_path))
            write_progress(output / "campaign.json", state)

    try:
        smoke_plan = plans / "P1-full-17"
        execute(
            "vidoclens.distillation.preflight",
            ["--plan-dir", smoke_plan, "--output", output / "preflight.json"],
        )
        for label, extra in (
            ("smoke", []),
            ("smoke-resumed", ["--resume", output / "smoke/checkpoint-0050"]),
        ):
            execute(
                "vidoclens.distillation.train",
                [
                    "--plan-dir",
                    smoke_plan,
                    "--output",
                    output / label,
                    "--seed",
                    17,
                    "--kind",
                    "smoke",
                    *extra,
                ],
            )
        execute(
            "vidoclens.distillation.verify_resume",
            [
                "--plan-dir",
                smoke_plan,
                "--continuous",
                output / "smoke",
                "--resumed",
                output / "smoke-resumed",
                "--output",
                output / "resume_proof.json",
            ],
        )
        proof = json.loads((output / "resume_proof.json").read_text(encoding="utf-8"))
        if proof.get("status") != "pass" or proof["plan_sha256"] != sha256(
            smoke_plan / "manifest.json"
        ):
            raise ValueError("mixed training smoke/resume gate failed")
        for seed in (17, 42, 2026):
            for arm in ("P1-full", "P1-size", "P2"):
                label = f"{arm}-{seed}"
                plan, training = plans / label, output / label
                execute(
                    "vidoclens.distillation.train",
                    ["--plan-dir", plan, "--output", training, "--seed", seed],
                )
                for step in (96, 191):
                    prediction = output / f"{label}-step{step}"
                    execute(
                        "vidoclens.distillation.predict",
                        [
                            "--plan-dir",
                            plan,
                            "--output",
                            prediction,
                            "--checkpoint",
                            training / f"checkpoint-{step:04d}",
                        ],
                    )
                    execute(
                        "vidoclens.eval.student",
                        [
                            "evaluate",
                            "--plan-dir",
                            plan,
                            "--run-dir",
                            prediction,
                            "--protocol-path",
                            plan / "dev_protocol.json",
                            "--output",
                            prediction / "metrics.json",
                        ],
                    )
        state["complete"] = True
    except BaseException as error:
        state["error"] = type(error).__name__
        raise
    finally:
        write_progress(output / "campaign.json", state)
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--plans", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
