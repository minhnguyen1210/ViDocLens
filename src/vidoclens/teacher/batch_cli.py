"""Batch CLI; preparation is offline, all upload/submit operations require explicit grants."""

import hashlib
import json
import os
from pathlib import Path

import typer

from vidoclens.common.pilot import sha256, write_json
from vidoclens.teacher.batch import TERMINAL, make_shards, reconcile_lines, submit_shard
from vidoclens.teacher.budget import reserve_cost
from vidoclens.teacher.cli import app, settings, validate_frozen_inputs
from vidoclens.teacher.engine import permission_errors, require_permission
from vidoclens.teacher.ledger import Ledger
from vidoclens.teacher.planning import read_plan
from vidoclens.teacher.provider import OpenAIProvider, response_json
from vidoclens.teacher.requests import canonical, request_key


@app.command("batch-prepare")
def prepare(
    plan_dir: Path,
    output: Path,
    root: Path = Path("."),
    config: Path = Path("configs/teacher/openai.yaml"),
    max_bytes: int = 190_000_000,
    max_input_tokens: int = 2_000_000,
    eligible_from: Path | None = None,
    dry_run: bool = False,
):
    """Create private JSONL shards by model/bytes/tokens; never upload them."""
    requests, prompt, _ = read_plan(root / plan_dir, root)
    if eligible_from is not None:
        report = json.loads((root / eligible_from).read_text(encoding="utf-8"))
        keys = set(report["resubmit_eligible"])
        requests = [r for r in requests if request_key(r, prompt) in keys]
        if not keys or len(requests) != len(keys):
            raise ValueError("eligible subset must be nonempty and belong to this plan")
    _, _, prices = settings(root, config, None)
    directory = root / output
    if not dry_run:
        directory.mkdir(parents=True, exist_ok=False)
    shards = []
    for index, shard in enumerate(
        make_shards(
            requests, prompt, root, prices, max_bytes=max_bytes, max_input_tokens=max_input_tokens
        )
    ):
        path = directory / f"shard_{index:04d}.jsonl"
        payload = b"".join(item[2] for item in shard)
        if not dry_run:
            with path.open("xb") as stream:
                stream.write(payload)
        shards.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "keys": [item[1] for item in shard],
            }
        )
    if dry_run:
        typer.echo(
            canonical(
                {
                    "shards": len(shards),
                    "bytes": sum(s["bytes"] for s in shards),
                    "api_calls": 0,
                    "dry_run": True,
                }
            )
        )
        return
    write_json(
        directory / "manifest.json",
        {
            "plan_sha256": sha256(root / plan_dir / "manifest.json"),
            "shards": shards,
            "max_bytes": max_bytes,
            "max_input_tokens": max_input_tokens,
        },
    )
    typer.echo(
        canonical({"shards": len(shards), "api_calls": 0, "contains_private_image_data": True})
    )


@app.command("batch-submit")
def submit(
    plan_dir: Path,
    batch_dir: Path,
    shard_index: int,
    journal: Path,
    root: Path = Path("."),
    config: Path = Path("configs/teacher/openai.yaml"),
    permission: Path | None = None,
    dry_run: bool = False,
):
    """Reserve and submit one shard. An ambiguous POST must be reconciled manually."""
    requests, prompt, _ = read_plan(root / plan_dir, root)
    cfg, grant, prices = settings(root, config, permission)
    manifest = json.loads((root / batch_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest["plan_sha256"] != sha256(root / plan_dir / "manifest.json"):
        raise ValueError("Batch belongs to another plan")
    if shard_index < 0 or shard_index >= len(manifest["shards"]):
        raise typer.BadParameter("invalid shard index")
    entry = manifest["shards"][shard_index]
    path = (root / batch_dir / entry["path"]).resolve()
    if not path.is_relative_to((root / batch_dir).resolve()) or sha256(path) != entry["sha256"]:
        raise ValueError("Batch file path/checksum invalid")
    by_key = {request_key(r, prompt): r for r in requests}
    rows = [by_key[k] for k in entry["keys"]]
    if dry_run:
        validate_frozen_inputs(rows, root)
        typer.echo(
            canonical(
                {
                    "api_calls": 0,
                    "dry_run": True,
                    "requests": len(rows),
                    "blockers": sorted(
                        {
                            e
                            for r in rows
                            for e in permission_errors(r, grant, prompt=prompt, batch=True)
                        }
                    ),
                    "reservation_micro_usd": sum(
                        reserve_cost(r.profile, prices[r.profile.model_snapshot], batch=True)
                        for r in rows
                    ),
                }
            )
        )
        return
    for request in rows:
        require_permission(request, grant, prompt=prompt, batch=True)
    validate_frozen_inputs(rows, root)
    lines = path.read_bytes().splitlines(keepends=True)
    shard = [(row, key, line) for row, key, line in zip(rows, entry["keys"], lines, strict=True)]
    ledger = Ledger(root / cfg["ledger_path"], grant.budget_micro_usd)
    provider = OpenAIProvider(os.environ.get("OPENAI_API_KEY", ""), timeout=cfg["timeout_seconds"])
    try:
        batch_id, _ = submit_shard(
            shard, prompt, grant, prices, ledger, provider, root / journal, root
        )
        typer.echo(canonical({"batch_id": batch_id, "journal": str(journal)}))
    finally:
        provider.close()


@app.command("batch-reconcile")
def reconcile(
    plan_dir: Path,
    journal: Path,
    output: Path,
    root: Path = Path("."),
    config: Path = Path("configs/teacher/openai.yaml"),
    permission: Path | None = None,
    delete_files: bool = False,
    reopen_unexecuted: bool = False,
):
    """Fetch a submitted Batch, reconcile terminal results; optionally delete its provider files."""
    requests, prompt, _ = read_plan(root / plan_dir, root)
    cfg, grant, prices = settings(root, config, permission)
    events = [
        json.loads(line) for line in (root / journal).read_text(encoding="utf-8").splitlines()
    ]
    submitted = [e for e in events if e["event"] == "submitted"]
    reserved = [e for e in events if e["event"] == "reserved"]
    if len(submitted) != 1 or len(reserved) != 1:
        raise ValueError("ambiguous/incomplete submission; use provider accounting before recovery")
    attempts = reserved[0]["attempts"]
    rows = [r for r in requests if request_key(r, prompt) in attempts]
    if len(rows) != len(attempts):
        raise ValueError("journal belongs to another plan")
    for request in rows:
        require_permission(request, grant, prompt=prompt, batch=True)
    ledger = Ledger(root / cfg["ledger_path"], grant.budget_micro_usd)
    provider = OpenAIProvider(os.environ.get("OPENAI_API_KEY", ""), timeout=cfg["timeout_seconds"])
    try:
        response = provider.get_batch(submitted[0]["batch_id"])
        response.raise_for_status()
        batch = response_json(response)
        if batch.get("status") not in TERMINAL:
            typer.echo(canonical({"status": batch.get("status"), "reservations_released": False}))
            return
        directory = root / output
        directory.mkdir(parents=True, exist_ok=False)
        write_json(directory / "provider_batch.json", batch)
        texts = {}
        for key in ("output_file_id", "error_file_id"):
            texts[key] = ""
            if batch.get(key):
                response = provider.get_file(batch[key])
                response.raise_for_status()
                texts[key] = response.text
                (directory / f"{key}.jsonl").write_text(response.text, encoding="utf-8")
        report = reconcile_lines(
            rows,
            prompt,
            batch_state=batch["status"],
            output=texts["output_file_id"],
            errors=texts["error_file_id"],
            prices=prices,
            ledger=ledger,
            attempts=attempts,
        )
        report["batch_id"] = batch["id"]
        report["files_deleted"] = []
        # Provider file deletion is limited to this submitted job and follows durable local copies.
        if delete_files:
            ids = {
                submitted[0]["input_file_id"],
                batch.get("output_file_id"),
                batch.get("error_file_id"),
            }
            for file_id in sorted(ids - {None}):
                response = provider.delete_file(file_id)
                if response.status_code not in {200, 404}:
                    response.raise_for_status()
                report["files_deleted"].append(file_id)
        if reopen_unexecuted:
            for key in report["resubmit_eligible"]:
                ledger.allow_batch_resubmit(key)
        write_json(directory / "reconciliation.json", report)
        typer.echo(
            canonical(
                {
                    k: len(report[k])
                    for k in (
                        "successful",
                        "failed",
                        "resubmit_eligible",
                        "missing_uncertain",
                    )
                }
            )
        )
    finally:
        provider.close()
