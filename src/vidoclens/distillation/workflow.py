"""Execute the authorized Phase 4 stages after a completed, unchanged local pilot.

All outputs are private local artifacts. No stage, commit, push, external API or hosting.
Human review is exported for the actual reviewer and never filled by this runner.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGenerationGrant, LocalTeacherPlan
from vidoclens.contracts.silver import SilverApproval, SilverPool
from vidoclens.distillation.inputs import source_paths
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.student.progress import write_progress


def run(root, pilot_run, train_ocr, ocr_python, output, selection_report, raw_mode=False):
    from vidoclens.eval.label_teacher_selection import verify_selection

    root = root.resolve()
    output, pilot_run, train_ocr = (root / p for p in (output, pilot_run, train_ocr))
    selection_report = root / selection_report
    selected = verify_selection(root, selection_report, pilot_run, raw_mode)
    if not (pilot_run / "manifest.json").is_file():
        raise ValueError("wait for the complete pilot before starting execution")
    output.mkdir(parents=True, exist_ok=False)
    state = {
        "complete": False,
        "human_review_complete": False,
        "g4_passed": False,
        "steps": [],
        "error": None,
        "pilot_manifest_sha256": sha256(pilot_run / "manifest.json"),
        "selection_report": selection_report.relative_to(root).as_posix(),
        "selection_report_sha256": sha256(selection_report),
    }
    children = []

    def execute(module, arguments, *, interpreter=None, background=False):
        command = [str(interpreter or sys.executable), "-u", "-m", module, *map(str, arguments)]
        entry = {"command": command, "exit_code": None}
        state["steps"].append(entry)
        log_path = output / f"stage-{len(state['steps']):02d}.log"
        log = log_path.open("x", encoding="utf-8")
        process = subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        item = (process, log, log_path, entry)
        children.append(item)
        entry["pid"] = process.pid
        write_progress(output / "workflow.json", state)
        print(
            json.dumps({"started": module, "stage": len(state["steps"]), "pid": process.pid}),
            flush=True,
        )
        if background:
            return item
        finish(item)

    def finish(item):
        process, log, log_path, entry = item
        try:
            code = process.wait()
        finally:
            log.close()
        entry.update(exit_code=process.returncode, log=log_path.name, log_sha256=sha256(log_path))
        write_progress(output / "workflow.json", state)
        if code:
            raise RuntimeError(
                "Phase 4 stage failed; inspect recorded local log before continuation"
            )

    archive, frozen, inventory = source_paths(root)
    common = ["--archive", archive, "--frozen", frozen, "--inventory", inventory]
    cohort = root / "artifacts/phase3/dev_protocol_v2.json"
    inputs = root / "artifacts/phase4/inputs_v1"
    protocol = root / "artifacts/phase4/teacher_protocol_v1"

    def teacher(partition):
        args = [
            *common,
            "--pool",
            inputs / f"{partition}.json",
            "--plan",
            output / "labeling" / f"{partition}_plan.json",
            "--grant",
            output / "labeling" / f"{partition}_grant.json",
            "--model",
            root / "artifacts/models/Qwen3-VL-4B-Instruct/ebb281ec70b05090aa6165b016eac8ec08e71b17",
            "--snapshot",
            protocol / "snapshot.json",
            "--image-root",
            inputs,
            "--image-map",
            protocol / f"{partition}_image_map.json",
            "--run-id",
            f"phase4-{partition}-v1",
            "--max-attempts",
            1,
            "--output",
            output / f"{partition}_teacher",
        ]
        if partition == "audit_holdout":
            args += ["--frozen-filter", output / "labeling/freeze/config.json"]
        execute(
            "vidoclens.teacher.raw_labels" if raw_mode else "vidoclens.teacher.local_labels",
            ["run", *args],
        )
        if not raw_mode:
            execute(
                "vidoclens.teacher.reparse",
                [
                    "--source-run",
                    output / f"{partition}_teacher",
                    "--output",
                    output / f"{partition}_parsed",
                ],
            )

    def filter_pool(partition, ocr_dir):
        exported = output / f"{partition}_ocr_export"
        execute(
            "vidoclens.ocr.export_pool",
            [
                "--pool-path",
                inputs / f"{partition}.json",
                "--ocr-dir",
                ocr_dir,
                "--output",
                exported,
            ],
        )
        execute(
            "vidoclens.filtering",
            [
                "filter",
                "--pool",
                inputs / f"{partition}.json",
                "--batch",
                output / f"{partition}_{'teacher' if raw_mode else 'parsed'}/batch.json",
                "--ocr",
                exported / "ocr.jsonl",
                "--config",
                output / "labeling/freeze/config.json",
                "--output",
                output / f"{partition}_bundle",
            ],
        )

    try:
        if raw_mode:
            pilot_options = ["--raw-mode"]
            pilot_batch = pilot_run / "batch.json"
        else:
            execute(
                "vidoclens.teacher.reparse",
                ["--source-run", pilot_run, "--output", output / "pilot_parsed"],
            )
            pilot_options = ["--parsed-dir", output / "pilot_parsed"]
            pilot_batch = output / "pilot_parsed/batch.json"
        execute(
            "vidoclens.eval.local_pilot",
            ["--run-dir", pilot_run, "--output", output / "pilot_report.json", *pilot_options],
        )
        pilot = json.loads((output / "pilot_report.json").read_text(encoding="utf-8"))
        if pilot != selected:
            raise ValueError("selected pilot does not replay before silver generation")
        if pilot["status"] != "pass":
            raise PermissionError(
                "local teacher failed preregistered viability gate; no silver generation"
            )
        execute(
            "vidoclens.filtering",
            [
                "grid",
                *common,
                "--evaluation-cohort",
                cohort,
                "--pool",
                inputs / "dev_select.json",
                "--batch",
                pilot_batch,
                "--ocr",
                root / "artifacts/phase4/dev_ocr_v1.jsonl",
                "--config",
                root / "configs/filtering/f1.yaml",
                "--output",
                output / "grid",
            ],
        )
        execute(
            "vidoclens.distillation.labeling",
            [
                "--pilot-report",
                output / "pilot_report.json",
                "--grid-dir",
                output / "grid",
                "--output",
                output / "labeling",
            ],
        )
        audit_ocr = execute(
            "vidoclens.ocr.quality",
            [
                "--root",
                root,
                "--split-dir",
                frozen,
                "--inventory-dir",
                inventory.parent,
                "--archive",
                root / "data/raw/receiptvqa/rotated_images.zip",
                "--output",
                output / "audit_ocr",
                "--partition",
                "audit_holdout",
                "--pool-path",
                inputs / "audit_holdout.json",
            ],
            interpreter=ocr_python,
            background=True,
        )
        teacher("audit_holdout")
        finish(audit_ocr)
        filter_pool("audit_holdout", output / "audit_ocr")
        execute(
            "vidoclens.filtering",
            [
                "audit",
                *common,
                "--bundle",
                output / "audit_holdout_bundle",
                "--quality-bins",
                output / "audit_holdout_ocr_export/quality_bins.json",
                "--output",
                output / "holdout_report.json",
            ],
        )
        execute(
            "vidoclens.filtering",
            [
                "review-export",
                *common,
                "--bundle",
                output / "audit_holdout_bundle",
                "--per-stratum",
                25,
                "--seed",
                42,
                "--output",
                output / "human_review",
            ],
        )
        execute(
            "vidoclens.distillation.review_page",
            [
                "--packet-dir",
                output / "human_review",
                "--image-root",
                inputs,
                "--image-map",
                protocol / "audit_holdout_image_map.json",
                "--output",
                output / "human_review/review.html",
            ],
        )
        print(
            json.dumps({"human_review_ready": str(output / "human_review/review.html")}), flush=True
        )
        teacher("train_fit")
        if not (train_ocr / "summary.json").is_file():
            raise RuntimeError(
                "full training OCR still incomplete; preserve labels and continue after OCR"
            )
        filter_pool("train_fit", train_ocr)
        pool = read_model(inputs / "train_fit.json", SilverPool)
        from vidoclens.teacher.reparse import verify

        plan_type = LocalTeacherPlan
        if raw_mode:
            from vidoclens.contracts.raw_teacher import RawTeacherPlan
            from vidoclens.contracts.silver import SilverBatch

            plan_type = RawTeacherPlan
            batch = read_model(output / "train_fit_teacher/batch.json", SilverBatch)
            source_batch_sha256 = digest(batch)
            approval_evidence = output / "train_fit_teacher/manifest.json"
        else:
            batch, reparse = verify(output / "train_fit_teacher", output / "train_fit_parsed")
            source_batch_sha256 = reparse.source_batch_sha256
            approval_evidence = output / "train_fit_parsed/manifest.json"
        plan = read_model(output / "train_fit_teacher/plan.json", plan_type)
        grant = read_model(output / "train_fit_teacher/grant.json", LocalGenerationGrant)
        manifest = json.loads(
            (output / "train_fit_teacher/manifest.json").read_text(encoding="utf-8")
        )
        if (
            batch.fixture_only
            or not manifest.get("complete")
            or manifest["batch_sha256"] != source_batch_sha256
            or batch.pool_sha256 != digest(pool)
            or grant.plan_sha256 != digest(plan)
            or not grant.quality_pilot_passed
        ):
            raise ValueError("actual completed local training label provenance invalid")
        write_model(
            output / "train_approval.json",
            SilverApproval(
                pool_sha256=digest(pool),
                batch_sha256=digest(batch),
                training_labels_allowed=True,
                data_rights_verified=grant.data_rights_verified,
                model_license_verified=grant.model_license_verified,
                quality_pilot_passed=True,
                approved_by="owner Phase4 task2026-11-03; exact completed local batch",
                evidence_sha256=sha256(approval_evidence),
            ),
        )
        execute(
            "vidoclens.distillation.data",
            [
                "--bundle",
                output / "train_fit_bundle",
                "--approval-path",
                output / "train_approval.json",
                "--inputs",
                inputs,
                "--output",
                output / "training_plans",
            ],
        )
        execute(
            "vidoclens.distillation.campaign",
            ["--plans", output / "training_plans", "--output", output / "campaign"],
        )
        execute(
            "vidoclens.distillation.results",
            [
                "--plans",
                output / "training_plans",
                "--campaign",
                output / "campaign",
                "--output",
                output / "results",
            ],
        )
        paths = [
            output / "results" / f"{arm}-{seed}.json"
            for arm in ("L2", "P1-full", "P1-size", "P2")
            for seed in (17, 42, 2026)
        ]
        execute(
            "vidoclens.filtering",
            [
                "compare",
                *common,
                "--evaluation-cohort",
                cohort,
                "--train-bundle",
                output / "train_fit_bundle",
                "--approval",
                output / "train_approval.json",
                "--training-profile",
                output / "training_plans/training_profile.json",
                "--optimizer-updates",
                191,
                "--pool",
                inputs / "dev_select.json",
                "--results",
                *paths,
                "--output",
                output / "comparison",
            ],
        )
        state["complete"] = True
        state["remaining"] = ["actual human annotations", "final code checks and G4 evidence audit"]
    except BaseException as error:
        state["error"] = type(error).__name__
        raise
    finally:
        for process, log, _, entry in children:
            if process.poll() is None:
                import signal

                process.send_signal(signal.SIGINT)
                process.wait()
            if not log.closed:
                log.close()
            if entry["exit_code"] is None:
                entry["exit_code"] = process.returncode
        write_progress(output / "workflow.json", state)
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ("pilot-run", "train-ocr", "ocr-python", "output", "selection-report"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--raw-mode", action="store_true")
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
