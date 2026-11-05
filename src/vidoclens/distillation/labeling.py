"""Prepare exact grants only after replayed local pilot and dev filter freeze."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGenerationGrant, LocalTeacherConfig
from vidoclens.contracts.silver import SilverPool
from vidoclens.eval.filter_grid import select_grid
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.teacher.local_labels import build_plan, validate_holdout


def choose_candidate(grid):
    rows = grid["candidates"]
    minimum_recall = rows["tau-000"]["overall"]["filter_recall"]
    if minimum_recall is None:
        raise ValueError("no correct dev labels; cannot select a useful filter")
    eligible = [
        name
        for name, row in rows.items()
        if row["overall"]["filter_precision"] is not None
        and row["overall"]["filter_recall"] is not None
        and row["overall"]["filter_recall"] >= minimum_recall
    ]
    if not eligible:
        raise ValueError("no retained dev evidence; cannot fabricate filter freeze")
    return min(
        eligible,
        key=lambda name: (
            -rows[name]["overall"]["filter_precision"],
            -rows[name]["overall"]["filter_recall"],
            -rows[name]["overall"]["retention"],
            rows[name]["threshold"],
        ),
    )


def prepare(root, pilot_report, grid_dir, output):
    root = root.resolve()
    pilot_report, grid_dir, output = (root / p for p in (pilot_report, grid_dir, output))
    pilot = json.loads(pilot_report.read_text(encoding="utf-8"))
    if pilot.get("status") != "pass" or not all(pilot.get("criteria", {}).values()):
        raise PermissionError("local teacher quality gate has not passed")
    grid = json.loads((grid_dir / "grid.json").read_text(encoding="utf-8"))
    if grid["batch_sha256"] != pilot["batch_sha256"] or grid["fixture_only"]:
        raise ValueError("grid must use the actual authorized teacher pilot")
    output.mkdir(parents=True, exist_ok=False)
    candidate = choose_candidate(grid)
    frozen = select_grid(
        grid_dir,
        candidate,
        output / "freeze",
        selected_by="assistant executing preregistered ADR-P4-003",
        rationale=(
            "Highest precision among recall >= exact-only; "
            "tie recall, retention, then smaller tau. "
            "Policy frozen before pilot outputs."
        ),
    )
    plan_builder = build_plan
    if pilot.get("generation_mode") == "raw_single_v1":
        from vidoclens.contracts.raw_teacher import RawTeacherConfig
        from vidoclens.teacher.raw_labels import build_plan as build_raw

        config = RawTeacherConfig.model_validate(pilot["generation_config"])
        plan_builder = build_raw
    else:
        config = LocalTeacherConfig.model_validate(pilot["generation_config"])
    for partition in ("train_fit", "audit_holdout"):
        pool = read_model(root / "artifacts/phase4/inputs_v1" / f"{partition}.json", SilverPool)
        plan = plan_builder(pool, config)
        validate_holdout(plan, frozen)
        write_model(output / f"{partition}_plan.json", plan)
        write_model(
            output / f"{partition}_grant.json",
            LocalGenerationGrant(
                plan_sha256=digest(plan),
                purpose="silver_generation",
                generation_allowed=True,
                data_rights_verified=True,
                model_license_verified=True,
                quality_pilot_passed=True,
                evidence_sha256=sha256(pilot_report),
                approved_by="owner Phase4 task2026-11-03; validated local pilot",
            ),
        )
    write_model(
        output / "manifest.json",
        {
            "complete": True,
            "pilot_sha256": sha256(pilot_report),
            "selected_candidate": candidate,
            "files": {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob("*.json")},
        },
    )
    print(json.dumps({"selected_candidate": candidate, "generation_executed": False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ("pilot-report", "grid-dir", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    prepare(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
