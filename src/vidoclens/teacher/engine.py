"""Gated teacher execution with exact cache replay and bounded, separately reserved retries."""

import random
import time
from pathlib import Path

from vidoclens.contracts.teacher import (
    TeacherPermission,
    TeacherPriceCard,
    TeacherRequest,
    TeacherResult,
)
from vidoclens.teacher.budget import actual_cost, reserve_cost
from vidoclens.teacher.ledger import BudgetExceeded, Ledger, RequestInFlight
from vidoclens.teacher.provider import parse_response, response_json, retry_delay
from vidoclens.teacher.requests import build_body, identity, request_key


def permission_errors(
    request: TeacherRequest, permission: TeacherPermission, *, prompt=None, batch=False
):
    permission = TeacherPermission.model_validate(permission.model_dump())
    errors = []
    for name in (
        "external_processing_allowed",
        "account_terms_reviewed",
        "retention_reviewed",
        "price_snapshot_approved",
    ):
        if not getattr(permission, name):
            errors.append(name)
    if not all((permission.approved_by, permission.approved_at, permission.evidence)):
        errors.append("approval_evidence")
    if permission.budget_micro_usd <= 0:
        errors.append("positive_budget")
    if request.archive_sha256 != permission.archive_sha256:
        errors.append("archive_permission_mismatch")
    if request.split_sha256 != permission.split_sha256:
        errors.append("split_permission_mismatch")
    if request.profile.model_snapshot not in permission.allowed_models:
        errors.append("model_permission")
    if prompt is None or request_key(request, prompt) not in permission.allowed_request_keys:
        errors.append("request_scope_permission")
    if request.profile.role == "label_teacher" and not permission.training_export_allowed:
        errors.append("training_export_allowed")
    if batch and not permission.batch_files_allowed:
        errors.append("batch_files_allowed")
    return errors


def require_permission(request, permission, *, prompt=None, batch=False):
    errors = permission_errors(request, permission, prompt=prompt, batch=batch)
    if errors:
        raise PermissionError("teacher blocked: " + ", ".join(errors))


def execute(
    request: TeacherRequest,
    prompt: str,
    *,
    root: Path,
    permission: TeacherPermission,
    price: TeacherPriceCard,
    ledger: Ledger,
    provider,
    max_retries=2,
    sleep=time.sleep,
    jitter=random.random,
) -> tuple[TeacherResult, bool]:
    """Provider is injected; offline tests cannot accidentally use the live network."""
    import httpx

    if not 0 <= max_retries <= 3:
        raise ValueError("retry count must be between 0 and 3")
    request = TeacherRequest.model_validate(request.model_dump())
    require_permission(request, permission, prompt=prompt)
    if ledger.summary()["cap_micro_usd"] != permission.budget_micro_usd:
        raise ValueError("ledger and permission budgets disagree")
    key = request_key(request, prompt)
    body = build_body(request, prompt, root)
    cached = ledger.cached(key)
    if cached is not None:
        return cached, True
    reserve = reserve_cost(request.profile, price)
    try:
        attempt = ledger.start(key, identity(request, prompt), reserve)
    except RequestInFlight:
        cached = ledger.cached(key)
        if cached is not None:
            return cached, True
        raise
    for retry in range(max_retries + 1):
        retry_after = None
        try:
            response = provider.response(body)
            raw = response_json(response)
            ledger.record_raw(attempt, {"http_status": response.status_code, "body": raw})
            if response.status_code == 200:
                result = parse_response(raw, request, key)
                cost = actual_cost(result.usage, price) if result.usage is not None else None
                if (
                    raw.get("model") != request.profile.model_snapshot
                    or raw.get("service_tier", "default") != "default"
                ):
                    cost = None
                ledger.finish(key, result, raw, attempt=attempt, actual=cost)
                return result, False
            status = response.status_code
            retryable = status == 429 or 500 <= status <= 599
            retry_after = response.headers.get("Retry-After")
            # Do not release ambiguous 5xx, redirects or connection losses.
            cost = 0 if status in {400, 401, 403, 404, 413, 422, 429} else None
            result = TeacherResult(
                request_key=key, status="provider_error", error_code=f"http_{status}"
            )
        except (httpx.TransportError, OSError):
            raw = {"transport_error": True}
            ledger.record_raw(attempt, raw)
            result = TeacherResult(
                request_key=key, status="transport_error", error_code="transport_outcome_unknown"
            )
            cost, retryable = None, True
        delay = retry_delay(retry_after, retry, jitter())
        # A Retry-After larger than the configured wait bound stops this run, never retries early.
        if not retryable or retry == max_retries or delay > 60:
            ledger.finish(key, result, raw, attempt=attempt, actual=cost)
            return result, False
        ledger.settle(attempt, cost, result.error_code)
        try:
            attempt = ledger.reserve_retry(key, reserve)
        except BudgetExceeded:
            result = result.model_copy(update={"error_code": "retry_budget_exhausted"})
            ledger.finish(key, result, raw)
            return result, False
        sleep(delay)
    raise AssertionError("unreachable")


def training_labels(request: TeacherRequest, result: TeacherResult, permission, prompt: str):
    """Only explicit train_fit silver outputs may cross the later SFT boundary."""
    require_permission(request, permission, prompt=prompt)
    if (
        request.purpose != "silver"
        or request.profile.role != "label_teacher"
        or not permission.training_export_allowed
    ):
        raise PermissionError("evaluation caches cannot be exported for training")
    if result.status != "ok" or result.request_key != request_key(request, prompt):
        raise ValueError("training export requires a successful matching result")
    return tuple(label for label in result.labels if label.answerable)
