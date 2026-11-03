"""Adopt completed evidence without rewriting an interrupted campaign's history.

This supports evaluation-only continuation after all training has completed.
It performs no model calls and does not resume or append partial predictions.
"""

import argparse
import json
import math
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.phase3 import (
    Phase3Continuation,
    Phase3EvidenceFile,
    Phase3RunEvidence,
)
from vidoclens.student.data import load_plan, safe_path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def expected_runs(seeds, total_updates):
    return (
        {"L1": "prediction"}
        | {f"L2_seed{seed}": "training" for seed in seeds}
        | {
            f"L2_seed{seed}_step{step}": "prediction"
            for seed in seeds
            for step in (math.ceil(total_updates / 2), total_updates)
        }
    )


def file_reference(root, path):
    path = safe_path(root, path)
    return Phase3EvidenceFile(path=path.relative_to(root).as_posix(), sha256=sha256(path))


def run_reference(root, path, kind, *, partial=False):
    path = safe_path(root, path)
    names = ["run.json", "profile.json"]
    if kind == "prediction":
        names.append("predictions.jsonl")
        if not partial:
            names.append("metrics.json")
    else:
        names.extend(["config.json", "learning_curve.jsonl", "reload_probe.json"])
        names.extend(p.name for p in path.glob("source_*.py"))
    return Phase3RunEvidence(
        directory=path.relative_to(root).as_posix(),
        files={name: sha256(path / name) for name in names},
    )


def verify_file(root, reference):
    path = safe_path(root, reference.path)
    if sha256(path) != reference.sha256:
        raise ValueError("continuation evidence checksum changed")
    return path


def verify_logs(directory, steps):
    if not steps:
        raise ValueError("execution has no recorded steps")
    for step in steps:
        if sha256(safe_path(directory, step["log"])) != step["log_sha256"]:
            raise ValueError("execution log changed")


def command_matches(root, step, module, flag, directory):
    command = step["command"]
    if command[1:3] != ["-m", module] or command.count(flag) != 1:
        return False
    index = command.index(flag) + 1
    return index < len(command) and safe_path(root, command[index]) == directory


def resolve(root, manifest, expected, plan_hash):
    """Validate provenance and return run directories; never waive a failed step."""
    if manifest.plan_sha256 != plan_hash or set(manifest.runs) != set(expected):
        raise ValueError("continuation plan or run population mismatch")
    parent_path = verify_file(root, manifest.parent_campaign)
    pause = read(verify_file(root, manifest.pause_event))
    execution_path = verify_file(root, manifest.execution)
    parent, execution = read(parent_path), read(execution_path)
    if (
        parent["complete"]
        or parent["plan_sha256"] != plan_hash
        or pause["reason"] != "explicit_user_requested_pause"
        or pause["campaign_sha256"] != manifest.parent_campaign.sha256
        or safe_path(root, pause["campaign"]) != parent_path
        or not execution["complete"]
        or execution["error"] is not None
        or execution["parent_sha256"] != manifest.parent_campaign.sha256
        or safe_path(root, execution["parent_campaign"]) != parent_path
    ):
        raise ValueError("unverified pause or incomplete continuation")
    verify_logs(parent_path.parent, parent["steps"])
    verify_logs(execution_path.parent, execution["steps"])
    if (
        any(s["exit_code"] != 0 for s in parent["steps"][:-1])
        or parent["steps"][-1]["exit_code"] != -2
        or any(s["exit_code"] != 0 for s in execution["steps"])
        or sha256(execution_path.parent / "execute.py") != execution["script_sha256"]
    ):
        raise ValueError("unexpected campaign failure or failed continuation step")
    interrupted = pause["interrupted_evaluation"]["name"]
    if set(manifest.replaced_incomplete_runs) != {interrupted}:
        raise ValueError("interrupted prediction evidence must be retained")
    old_ref = manifest.replaced_incomplete_runs[interrupted]
    old_dir = safe_path(root, old_ref.directory)
    if old_dir != parent_path.parent / interrupted or not command_matches(
        root, parent["steps"][-1], "vidoclens.student.predict", "--output", old_dir
    ):
        raise ValueError("partial run does not belong to parent campaign")
    for name, digest in old_ref.files.items():
        if sha256(safe_path(old_dir, name)) != digest:
            raise ValueError("partial evidence changed")
    old_run = read(old_dir / "run.json")
    if (
        old_run["complete"]
        or old_run["completed"] != pause["interrupted_evaluation"]["completed"]
        or old_run["expected"] != pause["interrupted_evaluation"]["expected"]
        or sha256(old_dir / "run.json") != pause["partial_run_sha256"]
        or sha256(old_dir / "predictions.jsonl") != pause["partial_predictions_sha256"]
        or old_run["predictions_sha256"] != pause["partial_predictions_sha256"]
    ):
        raise ValueError("pause does not bind the preserved partial predictions")
    directories, continued = {}, []
    for label, kind in expected.items():
        ref = manifest.runs[label]
        directory = safe_path(root, ref.directory)
        old = parent_path.parent / label
        old_complete = (old / "run.json").exists() and read(old / "run.json")["complete"]
        required = {"run.json", "profile.json"}
        if kind == "prediction":
            required |= {"metrics.json", "predictions.jsonl"}
        else:
            required |= {"config.json", "learning_curve.jsonl", "reload_probe.json"}
            required |= {"source_" + p.name for p in (root / "src/vidoclens/student").glob("*.py")}
        if set(ref.files) != required:
            raise ValueError("run evidence files incomplete")
        if old_complete:
            if directory != old:
                raise ValueError("cannot replace a completed parent run")
            jobs = (
                [("vidoclens.student.train", "--output")]
                if kind == "training"
                else [
                    ("vidoclens.student.predict", "--output"),
                    ("vidoclens.eval.student", "--run-dir"),
                ]
            )
            for module, flag in jobs:
                if (
                    sum(
                        command_matches(root, s, module, flag, directory)
                        for s in parent["steps"][:-1]
                    )
                    != 1
                ):
                    raise ValueError("adopted parent run lacks recorded execution")
        elif kind == "training" or directory != execution_path.parent / label:
            raise ValueError("only missing evaluations can be continued")
        else:
            continued.append(label)
        for name, digest in ref.files.items():
            if sha256(safe_path(directory, name)) != digest:
                raise ValueError("adopted run evidence changed")
        run = read(directory / "run.json")
        if not run["complete"] or run["error"] is not None or run["plan_sha256"] != plan_hash:
            raise ValueError("cannot adopt an incomplete or cross-plan run")
        directories[label] = directory
    # Bind every fresh prediction/evaluation pair to the recorded successful command.
    if len(execution["steps"]) != 2 * len(continued):
        raise ValueError("unexpected continuation execution population")
    for label in continued:
        for module, flag in [
            ("vidoclens.student.predict", "--output"),
            ("vidoclens.eval.student", "--run-dir"),
        ]:
            matches = []
            for step in execution["steps"]:
                if command_matches(root, step, module, flag, directories[label]):
                    matches.append(step)
            if len(matches) != 1:
                raise ValueError("fresh run lacks one successful recorded execution")
    return parent, directories


def build(root, plan_dir, campaign_dir, continuation_dir, pause_event, output):
    root = root.resolve()
    config, train, _, _ = load_plan(root, safe_path(root, plan_dir))
    total = math.ceil(len(train) * config.epochs / config.gradient_accumulation)
    expected = expected_runs(config.seeds, total)
    parent = safe_path(root, campaign_dir)
    continued = safe_path(root, continuation_dir)
    runs, partial = {}, {}
    for label, kind in expected.items():
        old = parent / label
        previous = read(old / "run.json") if (old / "run.json").exists() else None
        if previous and previous["complete"]:
            runs[label] = run_reference(root, old, kind)
        else:
            if kind == "training":
                raise ValueError("all training must be complete before evaluation continuation")
            if previous:
                partial[label] = run_reference(root, old, kind, partial=True)
            runs[label] = run_reference(root, continued / label, kind)
    manifest = Phase3Continuation(
        plan_sha256=sha256(safe_path(root, plan_dir) / "manifest.json"),
        parent_campaign=file_reference(root, parent / "campaign.json"),
        pause_event=file_reference(root, pause_event),
        execution=file_reference(root, continued / "execution.json"),
        runs=runs,
        replaced_incomplete_runs=partial,
    )
    resolve(root, manifest, expected, manifest.plan_sha256)
    write_json(safe_path(root, output), manifest.model_dump(mode="json"))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    for name in ["plan-dir", "campaign-dir", "continuation-dir", "pause-event", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    result = build(**vars(parser.parse_args()))
    print(
        json.dumps(
            {
                "adopted_runs": len(result.runs),
                "partial_runs_preserved": len(result.replaced_incomplete_runs),
            }
        )
    )


if __name__ == "__main__":
    main()
