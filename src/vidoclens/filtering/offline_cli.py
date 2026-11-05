"""Additional Phase 4 workflows isolated from Phase 3's trainer/CLI."""

import csv
import io
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import SilverApproval, SilverBatch, SilverPool
from vidoclens.contracts.silver_results import SilverTrainingResult
from vidoclens.contracts.silver_review import SilverHumanReview, SilverReviewPacket
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.eval.filter_grid import THRESHOLDS, run_grid, select_grid
from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
from vidoclens.eval.silver_comparison import compare_results
from vidoclens.eval.silver_review import make_review_packet, summarize_review
from vidoclens.filtering.bundle import load_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest, read_model, write_model, write_text_exclusive
from vidoclens.filtering.pool import make_pool

COMMANDS = {"grid", "grid-select", "review-export", "review-import", "compare"}


def register_offline(sub):
    grid = sub.add_parser("grid", help="Run all four F1 thresholds on the same dev_select inputs")
    for name in ("pool", "batch", "ocr", "config"):
        grid.add_argument("--" + name, type=Path, required=True)
    grid.add_argument("--quality-bins", type=Path)
    choose = sub.add_parser(
        "grid-select", help="Record owner rationale and freeze one dev candidate"
    )
    choose.add_argument("--grid", type=Path, required=True)
    choose.add_argument("--candidate", choices=THRESHOLDS, required=True)
    choose.add_argument("--selected-by", required=True)
    choose.add_argument("--rationale", required=True)
    export = sub.add_parser(
        "review-export", help="Seeded blind review packet and separate sampling key"
    )
    export.add_argument("--bundle", type=Path, required=True)
    export.add_argument("--per-stratum", type=int, default=25)
    export.add_argument("--seed", type=int, default=42)
    ingest = sub.add_parser(
        "review-import", help="Validate complete human annotations; never rewrite gold"
    )
    ingest.add_argument("--packet-dir", type=Path, required=True)
    ingest.add_argument("--review", type=Path, required=True)
    compare = sub.add_parser(
        "compare", help="Fairness checks and paired dev comparison of 12 training results"
    )
    for name in ("train-bundle", "approval", "training-profile", "pool"):
        compare.add_argument("--" + name, type=Path, required=True)
    compare.add_argument("--optimizer-updates", type=int, required=True)
    compare.add_argument("--results", type=Path, nargs="+", required=True)
    compare.add_argument("--resamples", type=int, default=2000)
    compare.add_argument("--bootstrap-seed", type=int, default=42)
    for child in (grid, export, compare):
        child.add_argument("--evaluation-cohort", type=Path)
        for name in ("archive", "frozen", "inventory"):
            child.add_argument("--" + name, type=Path, required=True)
    for child in (grid, choose, export, ingest, compare):
        child.add_argument("--output", type=Path, required=True)


def _gold(args, pool):
    if pool.partition not in {"dev_select", "audit_holdout"}:
        raise PermissionError("only dev_select/audit_holdout evaluator gold")
    if digest(
        make_pool(args.archive, args.frozen, args.inventory, pool.partition, args.evaluation_cohort)
    ) != digest(pool):
        raise ValueError("pool differs from frozen source data")
    qids = {s.question.qid for s in pool.samples}
    return [
        r
        for r in load_evaluation_gold(
            args.archive, load_frozen_plan(args.frozen, 10), partition=pool.partition
        )
        if r.qid in qids
    ]


def _ocr(bundle):
    return [
        OCRResult.model_validate(r)
        for r in json.loads((bundle / "ocr.json").read_text(encoding="utf-8"))
    ]


def run_offline(args):
    if args.command not in COMMANDS:
        return False
    if args.command == "grid":
        from vidoclens.filtering.__main__ import config_at

        pool = read_model(args.pool, SilverPool)
        if pool.partition != "dev_select":
            raise PermissionError("grid only accepts dev_select before gold access")
        ocr = [
            OCRResult.model_validate_json(line)
            for line in args.ocr.read_text(encoding="utf-8").splitlines()
        ]
        bins = (
            json.loads(args.quality_bins.read_text(encoding="utf-8")) if args.quality_bins else None
        )
        run_grid(
            pool,
            read_model(args.batch, SilverBatch),
            ocr,
            config_at(args.config),
            _gold(args, pool),
            args.output,
            quality_bins=bins,
        )
    elif args.command == "grid-select":
        select_grid(
            args.grid,
            args.candidate,
            args.output,
            selected_by=args.selected_by,
            rationale=args.rationale,
        )
    elif args.command == "review-export":
        pool, batch, run = load_bundle(args.bundle)
        packet, key, template = make_review_packet(
            pool,
            batch,
            run,
            _gold(args, pool),
            _ocr(args.bundle),
            per_stratum=args.per_stratum,
            seed=args.seed,
        )
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in (
            ("packet.json", packet),
            ("sampling_key.json", key),
            ("review_template.json", template),
        ):
            write_model(args.output / name, value)
        write_model(
            args.output / "manifest.json",
            {
                "protocol": "silver_review_export_v1",
                "complete": True,
                "files": {
                    n: sha256(args.output / n)
                    for n in ("packet.json", "sampling_key.json", "review_template.json")
                },
            },
        )
    elif args.command == "review-import":
        manifest = json.loads((args.packet_dir / "manifest.json").read_text(encoding="utf-8"))
        names = {"packet.json", "sampling_key.json", "review_template.json"}
        if (
            manifest.get("protocol") != "silver_review_export_v1"
            or manifest.get("complete") is not True
            or set(manifest.get("files", {})) != names
        ):
            raise ValueError("invalid review export manifest")
        if any(sha256(args.packet_dir / name) != manifest["files"][name] for name in names):
            raise ValueError("review export checksum mismatch; fill a COPY of template")
        packet = read_model(args.packet_dir / "packet.json", SilverReviewPacket)
        key = json.loads((args.packet_dir / "sampling_key.json").read_text(encoding="utf-8"))
        write_model(
            args.output, summarize_review(packet, key, read_model(args.review, SilverHumanReview))
        )
    elif args.command == "compare":
        pool = read_model(args.pool, SilverPool)
        if pool.partition != "dev_select":
            raise PermissionError("comparison only accepts dev_select before gold access")
        training_pool, batch, run = load_bundle(args.train_bundle)
        if digest(make_pool(args.archive, args.frozen, args.inventory, "train_fit")) != digest(
            training_pool
        ):
            raise ValueError("training pool differs from frozen data")
        plans = select_experiments(
            training_pool,
            batch,
            run,
            read_model(args.approval, SilverApproval),
            sha256(args.training_profile),
            args.optimizer_updates,
        )
        results = [read_model(p, SilverTrainingResult) for p in args.results]
        report = compare_results(
            training_pool,
            pool,
            _gold(args, pool),
            plans,
            results,
            resamples=args.resamples,
            bootstrap_seed=args.bootstrap_seed,
        )
        args.output.mkdir(parents=True, exist_ok=False)
        write_model(args.output / "comparison.json", report)
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["arm", "metric", "mean", "sample_std", "seeds", "fixture_only"])
        for arm, metrics in report["seed_summary"].items():
            for name, values in metrics.items():
                writer.writerow(
                    [
                        arm,
                        name,
                        values["mean"],
                        values["sample_std"],
                        "17/42/2026",
                        report["fixture_only"],
                    ]
                )
        write_text_exclusive(args.output / "seed_summary.csv", stream.getvalue())
        write_model(
            args.output / "manifest.json",
            {
                "complete": True,
                "fixture_only": report["fixture_only"],
                "files": {
                    n: sha256(args.output / n) for n in ("comparison.json", "seed_summary.csv")
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
    return True
