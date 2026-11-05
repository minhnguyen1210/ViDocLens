"""Offline Phase 4: python -m vidoclens.filtering --help. No model/API execution."""

import argparse
import json
from pathlib import Path

import yaml

from vidoclens.common.pilot import sha256
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import FilterConfig, SilverApproval, SilverBatch, SilverPool
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.eval.silver import audit_filter
from vidoclens.filtering.bundle import load_bundle, write_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.offline_cli import register_offline, run_offline
from vidoclens.filtering.pool import make_pool


def config_at(path):
    return FilterConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def check_frozen_inputs(args, pool):
    expected = make_pool(
        args.archive, args.frozen, args.inventory, pool.partition, args.evaluation_cohort
    )
    if digest(expected) != digest(pool):
        raise ValueError("stored pool differs from current frozen data")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register_offline(sub)
    prepare = sub.add_parser("prepare", help="Export question-only pool from frozen G10 inputs")
    prepare.add_argument(
        "--partition", choices=["train_fit", "dev_select", "audit_holdout"], required=True
    )
    run = sub.add_parser("filter", help="Import local runner outputs and compute F0/F1")
    for name in ("pool", "batch", "ocr", "config"):
        run.add_argument("--" + name, type=Path, required=True)
    freeze = sub.add_parser("freeze", help="Bind selected config to a dev_select audit report")
    freeze.add_argument("--config", type=Path, required=True)
    freeze.add_argument("--dev-report", type=Path, required=True)
    audit = sub.add_parser("audit", help="Evaluate with gold in privileged evaluator only")
    audit.add_argument(
        "--quality-bins", type=Path, help="Independent document_id -> quality bin JSON"
    )
    select = sub.add_parser("select", help="Prepare 9 selections; does not run/approve training")
    select.add_argument("--approval", type=Path, required=True)
    select.add_argument("--training-profile", type=Path, required=True)
    select.add_argument("--optimizer-updates", type=int, required=True)
    for child in (audit, select):
        child.add_argument("--bundle", type=Path, required=True)
    for child in (prepare, audit, select):
        child.add_argument("--evaluation-cohort", type=Path)
        for name in ("archive", "frozen", "inventory"):
            child.add_argument("--" + name, type=Path, required=True)
    for child in (prepare, run, freeze, audit, select):
        child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if run_offline(args):
        return
    if args.command == "prepare":
        write_model(
            args.output,
            make_pool(
                args.archive, args.frozen, args.inventory, args.partition, args.evaluation_cohort
            ),
        )
    elif args.command == "filter":
        ocr = [
            OCRResult.model_validate_json(line)
            for line in args.ocr.read_text(encoding="utf-8").splitlines()
        ]
        write_bundle(
            args.output,
            read_model(args.pool, SilverPool),
            read_model(args.batch, SilverBatch),
            ocr,
            config_at(args.config),
        )
    elif args.command == "freeze":
        config = config_at(args.config)
        report = json.loads(args.dev_report.read_text(encoding="utf-8"))
        if (
            config.status != "pilot_defaults_not_calibrated"
            or report.get("protocol") != "strict_nfc_em_filter_audit_v1"
            or report.get("partition") != "dev_select"
            or report.get("config_sha256") != digest(config)
        ):
            raise ValueError("freeze needs the selected config's dev_select evidence")
        frozen = FilterConfig.model_validate(
            config.model_dump()
            | {
                "status": "frozen_dev_select",
                "freeze_evidence_sha256": sha256(args.dev_report),
                "freeze_access_plan_sha256": report.get("access_plan_sha256"),
                "freeze_fixture_only": report.get("fixture_only"),
            }
        )
        write_model(args.output, frozen)
    else:
        pool, batch, run = load_bundle(args.bundle)
        check_frozen_inputs(args, pool)
        if args.command == "audit":
            # Reject train_fit before any privileged gold access.
            if pool.partition not in {"dev_select", "audit_holdout"}:
                raise PermissionError("only dev_select/audit_holdout filter quality")
            gold = load_evaluation_gold(
                args.archive, load_frozen_plan(args.frozen, 10), partition=pool.partition
            )
            bins = (
                json.loads(args.quality_bins.read_text(encoding="utf-8"))
                if args.quality_bins
                else None
            )
            gold = [r for r in gold if r.qid in {s.question.qid for s in pool.samples}]
            write_model(args.output, audit_filter(pool, batch, run, gold, quality_bins=bins))
        else:
            plans = select_experiments(
                pool,
                batch,
                run,
                read_model(args.approval, SilverApproval),
                sha256(args.training_profile),
                args.optimizer_updates,
            )
            args.output.mkdir(parents=True, exist_ok=False)
            for plan in plans:
                write_model(args.output / f"{plan.arm}-{plan.seed}.json", plan)
            # These are silver targets only. The Phase 3 loader retains privileged G10 access.
            write_model(
                args.output / "silver_targets.json",
                {
                    "pool_sha256": digest(pool),
                    "batch_sha256": digest(batch),
                    "fixture_only": batch.fixture_only,
                    "targets": {d.qid: d.answer_raw for d in run.decisions if d.f0_keep},
                },
            )
            write_model(
                args.output / "manifest.json",
                {
                    "complete": True,
                    "training_executed": False,
                    "requires_g3_validation": True,
                    "files": {
                        p.name: sha256(p) for p in sorted(args.output.iterdir()) if p.is_file()
                    },
                },
            )
    print(
        json.dumps(
            {
                "status": "written",
                "command": args.command,
                "output": str(args.output),
                "training_executed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
