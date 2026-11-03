"""Explicit teacher commands; estimate/preflight are entirely offline."""

import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import typer

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.teacher import (
    TeacherPermission,
    TeacherPriceCard,
    TeacherProfile,
    TeacherResult,
)
from vidoclens.teacher.budget import reserve_cost
from vidoclens.teacher.credentials import load_api_key
from vidoclens.teacher.engine import execute, permission_errors, require_permission
from vidoclens.teacher.ledger import Ledger
from vidoclens.teacher.planning import make_plan, read_plan
from vidoclens.teacher.provider import OpenAIProvider
from vidoclens.teacher.requests import canonical, request_key

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    help="Teacher plans, permission gates and metered execution.",
)


def settings(root, config: Path, permission: Path | None):
    import yaml

    cfg = yaml.safe_load((root / config).read_text(encoding="utf-8"))
    grant_path = permission or Path(cfg["permission_path"])
    grant = TeacherPermission.model_validate_json((root / grant_path).read_text(encoding="utf-8"))
    prices = {}
    for candidate in cfg["candidates"].values():
        card = TeacherPriceCard.model_validate_json(
            (root / candidate["price_card_path"]).read_text(encoding="utf-8")
        )
        if card.model_snapshot != candidate["model_snapshot"]:
            raise ValueError("configured model and price snapshot differ")
        prices[card.model_snapshot] = card
    return cfg, grant, prices


@app.command()
def plan(
    output: Path,
    root: Path = Path("."),
    split_dir: Path = Path("data/splits/receiptvqa_containment_v1"),
    archive: Path = Path("data/raw/receiptvqa/ReceiptVQA_annotations.zip"),
    train_ocr: Path = Path("artifacts/phase1/ocr_quality_v1"),
    dev_ocr: Path = Path("artifacts/phase2/dev_ocr_v1"),
    config: Path = Path("configs/teacher/openai.yaml"),
):
    """Freeze 50 integration/100 dev images and question chunks, without reading gold."""
    cfg, _, prices = settings(root, config, None)
    role = cfg["roles"]["benchmark_teacher"]
    profiles = {
        name: TeacherProfile(
            model_snapshot=cfg["candidates"][name]["model_snapshot"],
            role="benchmark_teacher",
            modality="image_ocr",
            prompt_version=role["prompt_version"],
            image_detail=role["image_detail"],
            max_output_tokens=role["max_output_tokens"],
            reasoning_effort=role["reasoning_effort"],
            store=cfg["store"],
        )
        for name in ("strong", "cheap")
    }
    for profile in profiles.values():
        reserve_cost(profile, prices[profile.model_snapshot])
    manifest = make_plan(
        root,
        root / split_dir,
        root / archive,
        root / train_ocr,
        root / dev_ocr,
        root / output,
        profiles=profiles,
    )
    typer.echo(
        canonical(
            {k: manifest[k] for k in ("counts", "questions_per_experiment", "input_has_gold")}
        )
    )


@app.command()
def estimate(
    plan_dir: Path,
    root: Path = Path("."),
    config: Path = Path("configs/teacher/openai.yaml"),
    permission: Path | None = None,
    output: Path | None = None,
):
    """Report permission blockers and conservative per-attempt bounds; no network/key access."""
    requests, prompt, manifest = read_plan(root / plan_dir, root)
    _, grant, prices = settings(root, config, permission)
    groups = {}
    for experiment in sorted({r.experiment for r in requests}):
        rows = [r for r in requests if r.experiment == experiment]
        amounts = [reserve_cost(r.profile, prices[r.profile.model_snapshot]) for r in rows]
        groups[experiment] = {
            "images": len({r.document_id for r in rows}),
            "requests": len(rows),
            "questions": sum(len(r.questions) for r in rows),
            "max_single_reservation_usd": max(amounts) / 1_000_000,
            "all_requests_upper_bound_usd_no_retries": sum(amounts) / 1_000_000,
        }
    errors = sorted(
        {error for r in requests for error in permission_errors(r, grant, prompt=prompt)}
    )
    report = {
        "status": "blocked" if errors else "permission_ready",
        "blockers": errors,
        "cap_usd": grant.budget_micro_usd / 1_000_000,
        "groups": groups,
        "billing_forecast": False,
        "reservation_policy": "full_model_input_at_max_tier_plus_output_cap",
        "account_model_access_verified": False,
        "api_calls": 0,
        "plan_sha256": sha256(root / plan_dir / "manifest.json"),
        "archive_sha256": manifest["archive_sha256"],
        "split_sha256": manifest["split_sha256"],
    }
    if output:
        write_json(root / output, report)
    typer.echo(json.dumps(report, indent=2))


def validate_frozen_inputs(requests, root: Path):
    """Recheck partition + original question text at live submission, never trust a flag alone."""
    from vidoclens.contracts.ingestion import CorpusImage
    from vidoclens.data.freeze import load_frozen_plan
    from vidoclens.data.receiptvqa import load_questions

    directory = root / "data/splits/receiptvqa_containment_v1"
    plan = load_frozen_plan(directory, 10)
    split_hash = sha256(directory / "summary.json")
    assignments = {a.source_image_id: a for a in plan.assignments}
    archive = root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip"
    if sha256(archive) != plan.archive_sha256:
        raise ValueError("annotation archive differs from frozen plan")
    inventory_path = root / "data/manifests/receiptvqa_ingestion_v1/images.jsonl"
    if sha256(inventory_path) != plan.image_inventory_sha256:
        raise ValueError("image inventory differs from frozen plan")
    inventory = {
        item.source_image_id: item
        for item in (
            CorpusImage.model_validate_json(line)
            for line in inventory_path.read_text(encoding="utf-8").splitlines()
        )
    }
    questions = {
        q.qid: q for split in ("train", "dev") for q in load_questions(archive, split=split)
    }
    for request in requests:
        if request.archive_sha256 != plan.archive_sha256 or request.split_sha256 != split_hash:
            raise ValueError("request not bound to frozen corpus")
        assignment = assignments.get(request.source_image_id)
        if assignment is None or assignment.partition != request.partition:
            raise PermissionError("request partition does not match frozen membership")
        image = inventory[request.source_image_id]
        if (
            image.document_id != request.document_id
            or image.raw_image_sha256 != request.image_sha256
        ):
            raise ValueError("request image differs from frozen inventory")
        path = (root / request.image_path).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != request.image_sha256:
            raise ValueError("image path or bytes changed")
        if request.purpose == "silver" and assignment.gold_for_training:
            raise PermissionError("silver input must exclude training gold groups")
        for q in request.questions:
            source = questions.get(q.qid)
            if (
                source is None
                or source.document_id != request.document_id
                or source.source_image_id != request.source_image_id
                or source.question_raw != q.question
            ):
                raise ValueError("request question differs from source")


@app.command()
def run(
    plan_dir: Path,
    output: Path,
    experiment: str = "pilot",
    root: Path = Path("."),
    config: Path = Path("configs/teacher/openai.yaml"),
    permission: Path | None = None,
    dry_run: bool = False,
    env_file: Path | None = None,
):
    """Execute an explicitly approved experiment; default only runs the 50-image pilot."""
    requests, prompt, _ = read_plan(root / plan_dir, root)
    rows = [r for r in requests if r.experiment == experiment]
    if not rows:
        raise typer.BadParameter("experiment absent from plan")
    cfg, grant, prices = settings(root, config, permission)
    if dry_run:
        validate_frozen_inputs(rows, root)
        typer.echo(
            canonical(
                {
                    "requests": len(rows),
                    "api_calls": 0,
                    "dry_run": True,
                    "blockers": sorted(
                        {e for r in rows for e in permission_errors(r, grant, prompt=prompt)}
                    ),
                    "max_reservation_micro_usd": max(
                        reserve_cost(r.profile, prices[r.profile.model_snapshot]) for r in rows
                    ),
                }
            )
        )
        return
    for request in rows:
        require_permission(request, grant, prompt=prompt)
        reserve_cost(request.profile, prices[request.profile.model_snapshot])
    validate_frozen_inputs(rows, root)
    directory = root / output
    directory.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(root / cfg["ledger_path"], grant.budget_micro_usd)
    # Credentials are consumed only after every permission/input gate passes. Never echo them.
    provider = None
    results, samples, cached_count = [], [], 0
    started_at = datetime.now(UTC).isoformat()
    ledger_before = ledger.summary()
    try:
        for i, request in enumerate(rows):
            started = time.perf_counter()
            key = request_key(request, prompt)
            cached = ledger.cached(key)
            if cached is not None:
                result, hit = cached, True
            else:
                if provider is None:
                    key_value = load_api_key(root, env_file)
                    provider = OpenAIProvider(key_value, timeout=cfg["timeout_seconds"])
                    del key_value
                result, hit = execute(
                    request,
                    prompt,
                    root=root,
                    permission=grant,
                    price=prices[request.profile.model_snapshot],
                    ledger=ledger,
                    provider=provider,
                    max_retries=cfg["max_retries"],
                )
            results.append(result)
            cached_count += hit
            samples.append(
                {
                    "request_key": key,
                    "source_image_id": request.source_image_id,
                    "cache_hit": hit,
                    "status": result.status,
                    "wall_seconds": time.perf_counter() - started,
                }
            )
            write_json(directory / f"{key}.json", result.model_dump(mode="json"))
            typer.echo(f"{experiment} {i + 1}/{len(rows)} {result.status} cache={hit}")
            if result.status in {
                "provider_error",
                "transport_error",
                "model_mismatch",
                "usage_error",
            }:
                raise RuntimeError(
                    "Provider/accounting failure; run stopped. Inspect retained status and ledger "
                    "before another submission."
                )
    finally:
        if provider is not None:
            provider.close()
        write_json(
            directory / "run.json",
            {
                "source": "openai_responses",
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "experiment": experiment,
                "plan_sha256": sha256(root / plan_dir / "manifest.json"),
                "permission_sha256": sha256(root / (permission or Path(cfg["permission_path"]))),
                "complete": len(results) == len(rows),
                "expected": len(rows),
                "completed": len(results),
                "status_counts": dict(Counter(r.status for r in results)),
                "cache_hits": cached_count,
                "samples": samples,
                "ledger_before": ledger_before,
                "price_cards": {
                    name: card.model_dump(mode="json") for name, card in prices.items()
                },
                "ledger": ledger.summary(),
                "files": {
                    f"{r.request_key}.json": sha256(directory / f"{r.request_key}.json")
                    for r in results
                },
            },
        )


@app.command()
def evaluate(plan_dir: Path, run_dirs: list[Path], output: Path, root: Path = Path(".")):
    """Read only dev_select gold after predictions exist; keep failures in the denominator."""
    from vidoclens.data.freeze import load_frozen_plan
    from vidoclens.eval.receiptvqa_gold import load_evaluation_gold
    from vidoclens.eval.teacher import evaluate_teacher

    requests, prompt, _ = read_plan(root / plan_dir, root)
    results = []
    for directory in run_dirs:
        directory = root / directory
        report = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        if report["plan_sha256"] != sha256(root / plan_dir / "manifest.json"):
            raise ValueError("run belongs to another plan")
        for name, expected in report["files"].items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory.resolve()) or sha256(path) != expected:
                raise ValueError("result checksum/path invalid")
            results.append(TeacherResult.model_validate_json(path.read_text(encoding="utf-8")))
    if not results:
        raise ValueError("no predictions; do not manufacture an empty baseline report")
    plan = load_frozen_plan(root / "data/splits/receiptvqa_containment_v1", 10)
    refs = load_evaluation_gold(
        root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", plan, partition="dev_select"
    )
    report = evaluate_teacher(requests, results, refs, prompt)
    report["plan_sha256"] = sha256(root / plan_dir / "manifest.json")
    write_json(root / output, report)
    typer.echo(json.dumps(report, indent=2))


@app.command()
def reconcile(
    ledger_path: Path,
    cap_micro_usd: int,
    attempt_id: str | None = None,
    actual_micro_usd: int | None = None,
    evidence: str | None = None,
):
    """Inspect unresolved attempts; settling requires an actual amount and evidence reference."""
    ledger = Ledger(ledger_path, cap_micro_usd)
    if attempt_id is not None:
        if actual_micro_usd is None or evidence is None:
            raise typer.BadParameter("amount and accounting evidence are required")
        ledger.reconcile_charge(attempt_id, actual_micro_usd, evidence)
    typer.echo(canonical({"summary": ledger.summary(), "unresolved": ledger.unresolved()}))
