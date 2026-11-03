"""Phase 5 CPU tooling: python -m vidoclens.verify --help. No model/API calls."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.calibration import RoutingGridPlan
from vidoclens.contracts.final_suite import FinalSuitePlan
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.ood_review import OODHumanSubmission, OODResolution, OODReviewPlan
from vidoclens.contracts.verification import (
    PipelineBinding,
    RoutingPolicy,
    VerificationBatch,
    VerificationPool,
    VerifierConfig,
    VerifierProfile,
)
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.eval.routing import routing_grid
from vidoclens.eval.verification import evaluate_verifier
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.verify.bundle import load_bundle, write_bundle
from vidoclens.verify.ood import reconcile, review_packets, submission_template
from vidoclens.verify.pool import make_pool
from vidoclens.verify.runtime import routing_implementation_hash
from vidoclens.verify.verifier import implementation_hash


def _gold(args, pool, profile):
    expected = make_pool(args.archive, args.frozen, args.inventory, pool.partition, profile=profile)
    if digest(pool) != digest(expected):
        raise ValueError("stored pool differs from frozen source")
    return load_evaluation_gold(
        args.archive, load_frozen_plan(args.frozen, 10), partition=pool.partition
    )


def _manifest(directory, protocol, names):
    write_model(
        directory / "manifest.json",
        {
            "protocol": protocol,
            "complete": True,
            "files": {name: sha256(directory / name) for name in names},
        },
    )


def _check(directory, protocol, names):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("protocol") != protocol
        or manifest.get("complete") is not True
        or set(manifest.get("files", {})) != set(names)
    ):
        raise ValueError("invalid artifact manifest")
    if any(sha256(directory / n) != manifest["files"][n] for n in names):
        raise ValueError("artifact checksum mismatch")


def _freeze_verifier(args):
    pool, student, ocr, profile, _ = load_bundle(args.bundle)
    if pool.partition != "dev_select" or profile.status != "candidate":
        raise PermissionError("verifier freeze needs candidate dev_select evidence")
    report = evaluate_verifier(pool, student, ocr, profile, _gold(args, pool, profile))
    selection = {
        "protocol": "verifier_selection_v1",
        "report": report,
        "selected_by": args.selected_by,
        "rationale": args.rationale,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write_model(args.output / "selection.json", selection)
    frozen = VerifierProfile.model_validate(
        profile.model_dump()
        | {
            "status": "frozen_dev_select",
            "selection_evidence_sha256": sha256(args.output / "selection.json"),
        }
    )
    write_model(args.output / "profile.json", frozen)
    _manifest(args.output, "verifier_freeze_v1", ("profile.json", "selection.json"))


def _routing_select(args):
    names = ("plan.json", "teacher.json", "report.json", "verification/manifest.json")
    _check(args.grid, "routing_grid_bundle_v1", names)
    pool, student, ocr, profile, _ = load_bundle(args.grid / "verification")
    teacher = read_model(args.grid / "teacher.json", VerificationBatch)
    plan = read_model(args.grid / "plan.json", RoutingGridPlan)
    report = json.loads((args.grid / "report.json").read_text(encoding="utf-8"))
    replay = routing_grid(pool, student, teacher, ocr, profile, plan, _gold(args, pool, profile))
    if report != replay:
        raise ValueError("routing grid replay differs")
    selected = next((p for p in report["points"] if p["threshold"] == args.threshold), None)
    if selected is None:
        raise ValueError("threshold not in registered routing grid")
    args.output.mkdir(parents=True, exist_ok=False)
    evidence = {
        "protocol": "routing_selection_v1",
        "grid_manifest_sha256": sha256(args.grid / "manifest.json"),
        "selected": selected,
        "selected_by": args.selected_by,
        "rationale": args.rationale,
        "fixture_only": plan.fixture_only,
        "targets_automatically_certified": False,
    }
    write_model(args.output / "selection.json", evidence)
    routing = RoutingPolicy(
        min_local_score=args.threshold,
        implementation_sha256=routing_implementation_hash(),
        verifier_profile_sha256=digest(profile),
        status="frozen_dev_calibrate",
        selection_evidence_sha256=sha256(args.output / "selection.json"),
        fixture_only=plan.fixture_only,
    )
    write_model(args.output / "routing.json", routing)
    write_model(args.output / "profile.json", profile)
    _manifest(args.output, "routing_freeze_v1", ("routing.json", "profile.json", "selection.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--partition", choices=("dev_select", "dev_calibrate"), required=True)
    prepare.add_argument("--profile", type=Path)
    candidate = sub.add_parser("profile")
    for name in ("pool", "binding"):
        candidate.add_argument("--" + name, type=Path, required=True)
    candidate.add_argument("--config", type=Path)
    run = sub.add_parser("verify")
    for name in ("pool", "student", "ocr", "profile"):
        run.add_argument("--" + name, type=Path, required=True)
    audit = sub.add_parser("audit")
    freeze = sub.add_parser("freeze-verifier")
    grid = sub.add_parser("routing-grid")
    grid.add_argument("--teacher", type=Path, required=True)
    grid.add_argument("--plan", type=Path, required=True)
    select = sub.add_parser("routing-select")
    select.add_argument("--grid", type=Path, required=True)
    select.add_argument("--threshold", type=float, required=True)
    for child in (audit, freeze, grid):
        child.add_argument("--bundle", type=Path, required=True)
    for child in (freeze, select):
        child.add_argument("--selected-by", required=True)
        child.add_argument("--rationale", required=True)
    for child in (prepare, audit, freeze, grid, select):
        for name in ("archive", "frozen", "inventory"):
            child.add_argument("--" + name, type=Path, required=True)
    ood_export = sub.add_parser("ood-packets")
    ood_import = sub.add_parser("ood-curate")
    for child in (ood_export, ood_import):
        child.add_argument("--plan", type=Path, required=True)
        child.add_argument("--inventory", type=Path, required=True)
    for name in ("primary", "second"):
        ood_import.add_argument("--" + name, type=Path, required=True)
    ood_import.add_argument("--resolutions", type=Path)
    final = sub.add_parser("preregister")
    for name in ("routing-freeze", "ood-curation", "systems", "frozen", "inventory"):
        final.add_argument("--" + name, type=Path, required=True)
    for child in (
        prepare,
        candidate,
        run,
        audit,
        freeze,
        grid,
        select,
        ood_export,
        ood_import,
        final,
    ):
        child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in {"freeze-verifier", "routing-select"} and (
        not args.selected_by.strip() or not args.rationale.strip()
    ):
        raise ValueError("selection needs reviewer and tradeoff rationale")
    if args.command == "prepare":
        profile = read_model(args.profile, VerifierProfile) if args.profile else None
        write_model(
            args.output,
            make_pool(args.archive, args.frozen, args.inventory, args.partition, profile=profile),
        )
    elif args.command == "profile":
        pool = read_model(args.pool, VerificationPool)
        if pool.partition != "dev_select":
            raise PermissionError("candidate profile selection belongs to dev_select")
        write_model(
            args.output,
            VerifierProfile(
                config=read_model(args.config, VerifierConfig) if args.config else VerifierConfig(),
                binding=read_model(args.binding, PipelineBinding),
                access_plan_sha256=pool.access_plan_sha256,
                implementation_sha256=implementation_hash(),
            ),
        )
    elif args.command == "verify":
        write_bundle(
            args.output,
            read_model(args.pool, VerificationPool),
            read_model(args.student, VerificationBatch),
            [
                OCRResult.model_validate_json(line)
                for line in args.ocr.read_text(encoding="utf-8").splitlines()
            ],
            read_model(args.profile, VerifierProfile),
        )
    elif args.command == "audit":
        pool, student, ocr, profile, _ = load_bundle(args.bundle)
        write_model(
            args.output, evaluate_verifier(pool, student, ocr, profile, _gold(args, pool, profile))
        )
    elif args.command == "freeze-verifier":
        _freeze_verifier(args)
    elif args.command == "routing-grid":
        pool, student, ocr, profile, _ = load_bundle(args.bundle)
        if pool.partition != "dev_calibrate":
            raise PermissionError("routing grid only on dev_calibrate")
        teacher, plan = (
            read_model(args.teacher, VerificationBatch),
            read_model(args.plan, RoutingGridPlan),
        )
        report = routing_grid(
            pool, student, teacher, ocr, profile, plan, _gold(args, pool, profile)
        )
        args.output.mkdir(parents=True, exist_ok=False)
        write_bundle(args.output / "verification", pool, student, ocr, profile)
        for name, value in (
            ("plan.json", plan),
            ("teacher.json", teacher),
            ("report.json", report),
        ):
            write_model(args.output / name, value)
        _manifest(
            args.output,
            "routing_grid_bundle_v1",
            ("plan.json", "teacher.json", "report.json", "verification/manifest.json"),
        )
    elif args.command == "routing-select":
        _routing_select(args)
    elif args.command == "ood-packets":
        plan = read_model(args.plan, OODReviewPlan)
        primary, second = review_packets(plan, args.inventory)
        args.output.mkdir(parents=True, exist_ok=False)
        for stage, packet in (("primary", primary), ("second", second)):
            write_model(args.output / f"{stage}_packet.json", packet)
            write_model(args.output / f"{stage}_template.json", submission_template(packet))
        _manifest(
            args.output,
            "ood_packets_v1",
            (
                "primary_packet.json",
                "primary_template.json",
                "second_packet.json",
                "second_template.json",
            ),
        )
    elif args.command == "ood-curate":
        plan = read_model(args.plan, OODReviewPlan)
        primary, second = (
            read_model(args.primary, OODHumanSubmission),
            read_model(args.second, OODHumanSubmission),
        )
        resolutions = (
            [
                OODResolution.model_validate(r)
                for r in json.loads(args.resolutions.read_text(encoding="utf-8"))
            ]
            if args.resolutions
            else []
        )
        report = reconcile(plan, args.inventory, primary, second, resolutions)
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in (
            ("plan.json", plan),
            ("primary.json", primary),
            ("second.json", second),
            ("resolutions.json", [r.model_dump(mode="json") for r in resolutions]),
            ("report.json", report),
        ):
            write_model(args.output / name, value)
        _manifest(
            args.output,
            "ood_curation_v1",
            ("plan.json", "primary.json", "second.json", "resolutions.json", "report.json"),
        )
    elif args.command == "preregister":
        _preregister(args)
    print(
        json.dumps(
            {
                "command": args.command,
                "status": "written",
                "output": str(args.output),
                "inference_executed": False,
                "g5_certified": False,
            }
        )
    )


def _preregister(args):
    _check(
        args.routing_freeze, "routing_freeze_v1", ("routing.json", "profile.json", "selection.json")
    )
    _check(
        args.ood_curation,
        "ood_curation_v1",
        ("plan.json", "primary.json", "second.json", "resolutions.json", "report.json"),
    )
    profile = read_model(args.routing_freeze / "profile.json", VerifierProfile)
    policy = read_model(args.routing_freeze / "routing.json", RoutingPolicy)
    access = load_frozen_plan(args.frozen, 10)
    if (
        profile.implementation_sha256 != implementation_hash()
        or policy.implementation_sha256 != routing_implementation_hash()
    ):
        raise ValueError("implementation changed after freeze")
    if (
        policy.verifier_profile_sha256 != digest(profile)
        or digest(access) != profile.access_plan_sha256
        or policy.selection_evidence_sha256 != sha256(args.routing_freeze / "selection.json")
    ):
        raise ValueError("freeze/access binding mismatch")
    ood = json.loads((args.ood_curation / "report.json").read_text(encoding="utf-8"))
    ood_plan = read_model(args.ood_curation / "plan.json", OODReviewPlan)
    if ood_plan.protected_inventory_sha256 != access.image_inventory_sha256:
        raise ValueError("OOD protected inventory differs from frozen corpus")
    replay = reconcile(
        ood_plan,
        args.inventory,
        read_model(args.ood_curation / "primary.json", OODHumanSubmission),
        read_model(args.ood_curation / "second.json", OODHumanSubmission),
        [
            OODResolution.model_validate(r)
            for r in json.loads(
                (args.ood_curation / "resolutions.json").read_text(encoding="utf-8")
            )
        ],
    )
    if replay != ood:
        raise ValueError("OOD curation replay differs")
    if (
        ood.get("protocol") != "human_ood_curation_v1"
        or ood.get("fixture_only") != policy.fixture_only
        or ood.get("human_review_requirement_met") is not True
    ):
        raise ValueError("OOD review/fixture provenance mismatch")
    from vidoclens.eval import metrics

    systems = json.loads(args.systems.read_text(encoding="utf-8"))
    if systems.get(
        "teacher-all"
    ) != profile.binding.fallback_profile_sha256 or profile.binding.student_bundle_sha256 not in [
        systems.get(f"P2/{seed}") for seed in (17, 42, 2026)
    ]:
        raise ValueError("system identities do not include the frozen pipeline")
    manifest = FinalSuitePlan(
        verifier=profile,
        routing=policy,
        frozen_access_plan_sha256=digest(access),
        test_image_ids=tuple(
            sorted(a.source_image_id for a in access.assignments if a.partition == "test")
        ),
        ood_curation_sha256=sha256(args.ood_curation / "report.json"),
        evaluator_source_sha256=sha256(Path(metrics.__file__)),
        systems=systems,
        fixture_only=policy.fixture_only,
    )
    write_model(args.output, manifest)


if __name__ == "__main__":
    main()
