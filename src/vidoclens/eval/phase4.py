"""Final G4 evidence audit; no generated success in the absence of human review."""

import argparse
import json
import tempfile
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.distillation import Phase4Criteria, Phase4GateReport
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import SilverApproval
from vidoclens.contracts.silver_review import SilverHumanReview, SilverReviewPacket
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.distillation.checks import source_hashes
from vidoclens.distillation.inputs import source_paths
from vidoclens.distillation.results import export
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.eval.silver import audit_filter
from vidoclens.eval.silver_comparison import compare_results
from vidoclens.eval.silver_review import make_review_packet, summarize_review
from vidoclens.filtering.bundle import load_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import read_model, write_model
from vidoclens.filtering.pool import make_pool
from vidoclens.student.data import safe_path


def preservation(root):
    path = root / "artifacts/phase4/integration_baseline_v1/preservation.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    for name, record in baseline["files"].items():
        current = safe_path(root, name)
        if (
            not current.is_file()
            or current.stat().st_size != record["bytes"]
            or sha256(current) != record["sha256"]
        ):
            raise ValueError("Phase3/frozen data/historical overview changed: " + name)
    return {"status": "pass", "files": len(baseline["files"]), "baseline_sha256": sha256(path)}


def run(root, execution, checks, output, human_review=None):
    root = root.resolve()
    execution, checks, output = (root / p for p in (execution, checks, output))
    preserved = preservation(root)
    verification = json.loads((checks / "checks.json").read_text(encoding="utf-8"))
    expected_checks = {"pytest", "ruff", "format", "doctor", "schemas", "repository"}
    if (
        verification.get("status") != "pass"
        or set(verification.get("checks", {})) != expected_checks
        or verification["source_hashes"] != source_hashes(root)
        or any(
            r["exit_code"] != 0 or sha256(checks / f"{name}.log") != r["log_sha256"]
            for name, r in verification["checks"].items()
        )
    ):
        raise ValueError("current code checks are missing, stale or failing")
    pilot = json.loads((execution / "pilot_report.json").read_text(encoding="utf-8"))
    from vidoclens.eval.label_teacher_selection import verify_selection
    from vidoclens.eval.local_pilot import run as evaluate_pilot

    workflow = json.loads((execution / "workflow.json").read_text(encoding="utf-8"))
    selection_path = root / workflow["selection_report"]
    if sha256(selection_path) != workflow["selection_report_sha256"]:
        raise ValueError("teacher selection record changed")
    raw_mode = pilot.get("generation_mode") == "raw_single_v1"
    selected = verify_selection(root, selection_path, root / pilot["source_run"], raw_mode)
    with tempfile.TemporaryDirectory(prefix="phase4-pilot-replay-") as temporary:
        replay_pilot = evaluate_pilot(
            root,
            Path(pilot["source_run"]),
            Path(temporary) / "pilot.json",
            parsed_dir=None if raw_mode else execution / "pilot_parsed",
            raw_mode=raw_mode,
        )
    if selected != pilot or replay_pilot != pilot:
        raise ValueError("selected teacher pilot does not replay")
    if pilot.get("status") != "pass" or not all(pilot["criteria"].values()):
        raise ValueError("actual local teacher gate failed")
    train_pool, batch, filtering = load_bundle(execution / "train_fit_bundle")
    from vidoclens.teacher.reparse import verify

    if pilot.get("generation_mode") != "raw_single_v1":
        replay_batch, _ = verify(execution / "train_fit_teacher", execution / "train_fit_parsed")
        if replay_batch != batch:
            raise ValueError("training labels differ from strict parsing of actual raw generations")
    else:
        from vidoclens.teacher.raw_replay import replay_completed

        if replay_completed(root, execution / "train_fit_teacher", train_pool) != batch:
            raise ValueError("raw training labels do not replay")
    archive, frozen, inventory = source_paths(root)
    if batch.fixture_only or train_pool != make_pool(archive, frozen, inventory, "train_fit"):
        raise ValueError("full real training pool provenance mismatch")
    audit_pool, audit_batch, audit_run = load_bundle(execution / "audit_holdout_bundle")
    if pilot.get("generation_mode") == "raw_single_v1":
        replay_audit = replay_completed(
            root, execution / "audit_holdout_teacher", audit_pool, audit_run.config
        )
    else:
        replay_audit, _ = verify(
            execution / "audit_holdout_teacher", execution / "audit_holdout_parsed"
        )
    if replay_audit != audit_batch:
        raise ValueError("audit labels differ from strict parsing of actual raw generations")
    if (
        audit_batch.fixture_only
        or audit_pool != make_pool(archive, frozen, inventory, "audit_holdout")
        or audit_run.config != filtering.config
        or audit_run.config.status != "frozen_dev_select"
    ):
        raise ValueError("audit and training must use the same frozen real filter")
    gold = load_evaluation_gold(archive, load_frozen_plan(frozen, 10), partition="audit_holdout")
    bins = json.loads(
        (execution / "audit_holdout_ocr_export/quality_bins.json").read_text(encoding="utf-8")
    )
    holdout = audit_filter(audit_pool, audit_batch, audit_run, gold, quality_bins=bins)
    if holdout != json.loads((execution / "holdout_report.json").read_text(encoding="utf-8")):
        raise ValueError("holdout metrics do not replay")
    from vidoclens.distillation.smoke_evidence import verify as verify_smoke

    verify_smoke(root, execution / "training_plans", execution / "campaign")
    with tempfile.TemporaryDirectory(prefix="phase4-final-replay-") as temporary:
        results = export(
            root, execution / "training_plans", execution / "campaign", Path(temporary) / "results"
        )
    plans = select_experiments(
        train_pool,
        batch,
        filtering,
        read_model(execution / "train_approval.json", SilverApproval),
        sha256(execution / "training_plans/training_profile.json"),
        191,
    )
    dev = make_pool(
        archive, frozen, inventory, "dev_select", root / "artifacts/phase3/dev_protocol_v2.json"
    )
    qids = {s.question.qid for s in dev.samples}
    dev_gold = [
        r
        for r in load_evaluation_gold(archive, load_frozen_plan(frozen, 10), partition="dev_select")
        if r.qid in qids
    ]
    comparison = compare_results(train_pool, dev, dev_gold, plans, results)
    if comparison != json.loads(
        (execution / "comparison/comparison.json").read_text(encoding="utf-8")
    ):
        raise ValueError("core comparison does not replay from actual trajectories")
    reviewed = False
    review_summary = None
    if human_review is not None:
        packet_dir = execution / "human_review"
        packet = read_model(packet_dir / "packet.json", SilverReviewPacket)
        key = json.loads((packet_dir / "sampling_key.json").read_text(encoding="utf-8"))
        ocr = [
            OCRResult.model_validate(r)
            for r in json.loads(
                (execution / "audit_holdout_bundle/ocr.json").read_text(encoding="utf-8")
            )
        ]
        replay_packet, replay_key, _ = make_review_packet(
            audit_pool, audit_batch, audit_run, gold, ocr, per_stratum=25, seed=42
        )
        if packet != replay_packet or key != replay_key:
            raise ValueError("human review sampling does not replay from frozen holdout")
        review = read_model(root / human_review, SilverHumanReview)
        review_summary = summarize_review(packet, key, review)
        reviewed = not review.fixture_only and review_summary["human_attestation_received"]
    evidence_paths = [
        execution / "pilot_report.json",
        selection_path,
        execution / "labeling/freeze/config.json",
        execution / "holdout_report.json",
        execution / "train_fit_teacher/manifest.json",
        execution / "audit_holdout_teacher/manifest.json",
        execution / "campaign/resume_proof.json",
        execution / "results/manifest.json",
        execution / "comparison/comparison.json",
        checks / "checks.json",
        root / "artifacts/phase4/integration_baseline_v1/preservation.json",
    ]
    if human_review is not None:
        evidence_paths.append(root / human_review)
    primary = comparison["paired_em"]["P2_vs_P1-size"]["training_seed_delta_mean"]
    report = Phase4GateReport(
        status="pass" if reviewed else "incomplete",
        criteria=Phase4Criteria(
            phase3_preserved=preserved["status"] == "pass",
            local_teacher_pilot=True,
            full_silver_provenance=True,
            frozen_filter_and_holdout_replay=True,
            human_error_review=reviewed,
            matched_three_seed_training=True,
            mixed_sampler_resume=True,
            twelve_result_comparison=True,
            code_checks=True,
            restricted_data_boundaries=True,
        ),
        evidence={str(p): sha256(p) for p in evidence_paths},
        h2_primary_difference=primary,
        limitations=(
            "dev results, not final test confirmation",
            "fixed-seed group CI excludes training variance",
            "silver arms3056 exposures vs historical L2 3053; all191updates",
            "lexical F1 is not semantic verification",
            "OCR confidence bins are uncalibrated proxies",
        ),
    )
    write_model(output, report)
    if review_summary is not None:
        write_model(output.with_name(output.stem + "_human_review.json"), review_summary)
    print(
        json.dumps(
            {
                "gate": "G4",
                "status": report.status,
                "h2_primary_difference": primary,
                "human_review_received": reviewed,
            }
        ),
        flush=True,
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ("execution", "checks", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--human-review", type=Path)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
