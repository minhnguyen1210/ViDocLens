"""Local label workflow; never downloads weights or calls paid providers."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import (
    LocalGenerationGrant,
    LocalModelSnapshot,
    LocalTeacherConfig,
    LocalTeacherPlan,
)
from vidoclens.contracts.silver import FilterConfig, SilverPool
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.pool import make_pool
from vidoclens.teacher.local_labels import build_plan, check_grant, run_local, validate_holdout
from vidoclens.teacher.local_qwen import (
    QwenLocalBackend,
    runtime_environment,
    snapshot_files,
    validate_snapshot,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot", help="Hash an existing dedicated local model directory")
    snapshot.add_argument("--model", type=Path, required=True)
    snapshot.add_argument("--model-id", required=True)
    snapshot.add_argument("--revision", required=True)
    configure = sub.add_parser("config", help="Create candidate defaults bound to a local snapshot")
    configure.add_argument("--snapshot", type=Path, required=True)
    plan = sub.add_parser("plan", help="Question-only deterministic requests, no inference")
    plan.add_argument("--config", type=Path, required=True)
    run = sub.add_parser("run", help="Opt-in real local GPU inference; resume exact run only")
    for name in ("plan", "grant", "model", "snapshot", "image-root", "image-map"):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--frozen-filter", type=Path)
    run.add_argument("--run-id", required=True)
    run.add_argument("--max-attempts", type=int, default=1)
    for child in (plan, run):
        child.add_argument("--evaluation-cohort", type=Path)
        for name in ("pool", "archive", "frozen", "inventory"):
            child.add_argument("--" + name, type=Path, required=True)
    for child in (snapshot, configure, plan, run):
        child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "config":
        snapshot = read_model(args.snapshot, LocalModelSnapshot)
        write_model(
            args.output,
            LocalTeacherConfig(
                model_id=snapshot.model_id,
                model_revision=snapshot.model_revision,
                snapshot_manifest_sha256=sha256(args.snapshot),
            ),
        )
    elif args.command == "snapshot":
        if args.output.resolve().is_relative_to(args.model.resolve()):
            raise ValueError("write snapshot manifest outside model directory")
        result = LocalModelSnapshot(
            model_id=args.model_id, model_revision=args.revision, files=snapshot_files(args.model)
        )
        write_model(args.output, result)
    else:
        pool = read_model(args.pool, SilverPool)
        if digest(
            make_pool(
                args.archive, args.frozen, args.inventory, pool.partition, args.evaluation_cohort
            )
        ) != digest(pool):
            raise ValueError("pool differs from frozen source inputs")
        if args.command == "plan":
            write_model(args.output, build_plan(pool, read_model(args.config, LocalTeacherConfig)))
        else:
            plan = read_model(args.plan, LocalTeacherPlan)
            if plan.fixture_only:
                raise PermissionError("real GPU CLI cannot execute synthetic plans")
            grant = read_model(args.grant, LocalGenerationGrant)
            check_grant(plan, grant)
            # All plan/scope checks precede optional ML imports/model loading.
            if digest(build_plan(pool, plan.config)) != digest(plan):
                raise ValueError("local plan changed")
            frozen = read_model(args.frozen_filter, FilterConfig) if args.frozen_filter else None
            validate_holdout(plan, frozen)
            mapping = json.loads(args.image_map.read_text(encoding="utf-8"))
            root = args.image_root.resolve(strict=True)
            images = {}
            for doc, relative in mapping.items():
                if not isinstance(relative, str) or Path(relative).is_absolute():
                    raise ValueError("image map requires relative paths")
                path = (root / relative).resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError("image path escapes approved root")
                images[doc] = path
            validate_snapshot(args.model, args.snapshot, plan.config)
            _, result = run_local(
                pool,
                plan,
                grant,
                QwenLocalBackend(args.model, plan.config),
                images,
                runtime_environment(),
                args.output,
                run_id=args.run_id,
                max_attempts=args.max_attempts,
                frozen_filter=frozen,
            )
            print(json.dumps(result))
            return
    print(
        json.dumps(
            {
                "status": "written",
                "command": args.command,
                "output": str(args.output),
                "inference_executed": False,
            }
        )
    )
