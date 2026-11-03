"""Batch preparation, submission journal and terminal reconciliation.

Unknown outcomes are held, never interpreted as a free missing response. This
module deliberately has no automatic submit retry after an ambiguous POST.
"""

import json
import os
from pathlib import Path

from vidoclens.contracts.teacher import TeacherResult
from vidoclens.teacher.budget import actual_cost, reserve_cost
from vidoclens.teacher.engine import require_permission
from vidoclens.teacher.ledger import RequestInFlight
from vidoclens.teacher.provider import parse_response, response_json
from vidoclens.teacher.requests import build_body, canonical, identity, request_key

TERMINAL = {"completed", "expired", "cancelled", "failed"}


def make_shards(
    requests,
    prompt,
    root,
    prices,
    *,
    max_bytes=190_000_000,
    max_input_tokens=2_000_000,
    max_requests=50000,
):
    if not 0 < max_bytes <= 200_000_000 or not 0 < max_requests <= 50000 or max_input_tokens <= 0:
        raise ValueError("invalid Batch shard limits")
    seen, shard, size, tokens, model = set(), [], 0, 0, None
    for request in requests:
        key = request_key(request, prompt)
        if key in seen:
            raise ValueError("duplicate Batch custom_id")
        seen.add(key)
        row = {
            "custom_id": key,
            "method": "POST",
            "url": "/v1/responses",
            "body": build_body(request, prompt, root),
        }
        encoded = (canonical(row) + "\n").encode("utf-8")
        # Full model limit is also a conservative enqueued-token bound, not a forecast.
        bound = prices[request.profile.model_snapshot].max_input_tokens
        if len(encoded) > max_bytes or bound > max_input_tokens:
            raise ValueError("one request exceeds shard byte/token limit")
        if shard and (
            size + len(encoded) > max_bytes
            or tokens + bound > max_input_tokens
            or len(shard) >= max_requests
            or model != request.profile.model_snapshot
        ):
            yield shard
            shard, size, tokens = [], 0, 0
        shard.append((request, key, encoded))
        size += len(encoded)
        tokens += bound
        model = request.profile.model_snapshot
    if shard:
        yield shard


def _journal(path: Path, event: dict):
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def submit_shard(shard, prompt, permission, prices, ledger, provider, journal: Path, root: Path):
    if journal.exists():
        raise ValueError("journal exists; reconcile it instead of submitting again")
    entries = []
    for request, key, encoded in shard:
        require_permission(request, permission, prompt=prompt, batch=True)
        if key != request_key(request, prompt):
            raise ValueError("shard request key changed")
        row = json.loads(encoded)
        if row != {
            "custom_id": key,
            "method": "POST",
            "url": "/v1/responses",
            "body": build_body(request, prompt, root),
        }:
            raise ValueError("custom ID mismatch")
        entries.append(
            (
                key,
                identity(request, prompt),
                reserve_cost(request.profile, prices[request.profile.model_snapshot], batch=True),
            )
        )
    if ledger.summary()["cap_micro_usd"] != permission.budget_micro_usd:
        raise ValueError("ledger and approved budget disagree")
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("x", encoding="utf-8"):
        pass
    attempts = ledger.start_many(entries)
    _journal(journal, {"event": "reserved", "attempts": attempts})
    # A crash at any following boundary leaves durable reservations and journal evidence.
    response = provider.upload_batch(b"".join(row[2] for row in shard))
    uploaded = response_json(response)
    if response.status_code != 200 or not isinstance(uploaded.get("id"), str):
        _journal(
            journal, {"event": "upload_failed_or_uncertain", "http_status": response.status_code}
        )
        raise RuntimeError("Batch upload failed; inspect journal and reconcile before retry")
    file_id = uploaded["id"]
    _journal(journal, {"event": "uploaded", "input_file_id": file_id})
    response = provider.create_batch(file_id)
    batch = response_json(response)
    if response.status_code != 200 or not isinstance(batch.get("id"), str):
        _journal(
            journal, {"event": "submit_failed_or_uncertain", "http_status": response.status_code}
        )
        raise RuntimeError("Batch creation failed; possible charge, no automatic resubmit")
    _journal(journal, {"event": "submitted", "batch_id": batch["id"], "input_file_id": file_id})
    return batch["id"], attempts


def reconcile_lines(
    requests, prompt, *, batch_state: str, output: str, errors: str, prices, ledger, attempts: dict
):
    if batch_state not in TERMINAL:
        raise ValueError("Batch is not terminal; keep every reservation")
    expected = {request_key(r, prompt): r for r in requests}
    if len(expected) != len(requests) or set(attempts) != set(expected):
        raise ValueError("Batch manifest/attempt mismatch")
    ledger.validate_attempt_mapping(attempts)
    records = {}
    # Validate the entire response set before mutating any accounting state.
    for line in (output + "\n" + errors).splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or not isinstance(record.get("custom_id"), str):
            raise ValueError("Batch record must have a string custom_id")
        key = record.get("custom_id")
        if key not in expected or key in records:
            raise ValueError("unknown or duplicate Batch custom_id")
        records[key] = record
    report = {"successful": [], "failed": [], "resubmit_eligible": [], "missing_uncertain": []}
    for key, request in expected.items():
        try:
            cached = ledger.cached(key)
        except RequestInFlight:
            cached = None
        if cached is not None:
            category = "successful" if cached.status == "ok" else "failed"
            report[category].append(key)
            if cached.error_code == "batch_not_executed":
                report["resubmit_eligible"].append(key)
            continue
        record = records.get(key)
        cost = None
        if record is None:
            result = TeacherResult(
                request_key=key, status="provider_error", error_code="batch_missing_unknown_charge"
            )
            report["missing_uncertain"].append(key)
        elif (
            isinstance(record.get("error"), dict)
            and record["error"].get("code") == "batch_expired"
            and record.get("response") is None
        ):
            cost = 0
            result = TeacherResult(
                request_key=key, status="provider_error", error_code="batch_not_executed"
            )
            report["resubmit_eligible"].append(key)
        elif (
            isinstance(record.get("response"), dict)
            and record["response"].get("status_code") == 200
        ):
            raw = record["response"].get("body")
            result = parse_response(raw, request, key)
            if (
                result.usage
                and raw.get("model") == request.profile.model_snapshot
                and raw.get("service_tier", "default") == "default"
            ):
                cost = actual_cost(result.usage, prices[request.profile.model_snapshot], batch=True)
        else:
            result = TeacherResult(
                request_key=key, status="provider_error", error_code="batch_error"
            )
        ledger.record_raw(attempts[key], record or {"missing_from_terminal_batch": True})
        ledger.finish(key, result, record or {}, attempt=attempts[key], actual=cost)
        report["successful" if result.status == "ok" else "failed"].append(key)
    report["ledger"] = ledger.summary()
    return report
