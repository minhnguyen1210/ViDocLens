"""Injected fallback orchestration. No HTTP client, credentials or model imports."""

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Protocol

from vidoclens.contracts.cascade import CascadeOutcome, FallbackReply, FallbackRequest
from vidoclens.filtering.io import digest, revalidate
from vidoclens.verify.verifier import implementation_hash, verify


def routing_implementation_hash():
    root = Path(__file__).resolve().parents[1]
    paths = [
        Path(__file__),
        root / "eval/routing.py",
        root / "contracts/cascade.py",
        root / "contracts/verification.py",
        root / "contracts/calibration.py",
    ]
    return digest([p.read_text(encoding="utf-8") for p in paths])


class FallbackBackend(Protocol):
    fixture_only: bool
    profile_sha256: str

    def complete(self, request: FallbackRequest, *, timeout_seconds: float) -> FallbackReply:
        """Honor the remaining timeout, one transport attempt, and exact image bytes hash."""
        ...


class BudgetCache:
    """Durable, single-attempt reservations. Unknown cost remains held after failures."""

    def __init__(self, path, cap_micro_usd):
        if type(cap_micro_usd) is not int or cap_micro_usd < 0:
            raise ValueError("invalid cap")
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS budget "
                "(id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER)"
            )
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, ?)", (cap_micro_usd,))
            if db.execute("SELECT cap FROM budget").fetchone()[0] != cap_micro_usd:
                raise ValueError("budget cap is immutable")
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls "
                "(key TEXT PRIMARY KEY, reserve INTEGER, actual INTEGER, reply TEXT, checksum TEXT)"
            )

    def begin(self, key, reserve):
        if type(reserve) is not int or reserve <= 0:
            raise ValueError("positive approved reservation required")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT reply, checksum FROM calls WHERE key=?", (key,)).fetchone()
            if row:
                if row[0] is None:
                    raise PermissionError("request_inflight_or_uncertain")
                reply = FallbackReply.model_validate_json(row[0])
                if reply.request_sha256 != key or digest(reply) != row[1]:
                    raise ValueError("fallback cache corrupted")
                return reply
            cap = db.execute("SELECT cap FROM budget").fetchone()[0]
            used = db.execute(
                "SELECT COALESCE(SUM(COALESCE(actual,reserve)),0) FROM calls"
            ).fetchone()[0]
            if used + reserve > cap:
                raise PermissionError("budget_exhausted")
            db.execute("INSERT INTO calls(key,reserve) VALUES (?,?)", (key, reserve))
        return None

    def finish(self, reply):
        reply = revalidate(reply)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT reserve, reply FROM calls WHERE key=?", (reply.request_sha256,)
            ).fetchone()
            if row is None or row[1] is not None:
                raise ValueError("reservation missing/already settled")
            overflow = (
                reply.actual_cost_micro_usd is not None and reply.actual_cost_micro_usd > row[0]
            )
            stored = (
                reply.model_copy(update={"status": "provider_error", "prediction": None})
                if overflow
                else reply
            )
            db.execute(
                "UPDATE calls SET actual=?, reply=?, checksum=? WHERE key=?",
                (
                    stored.actual_cost_micro_usd,
                    stored.model_dump_json(),
                    digest(stored),
                    stored.request_sha256,
                ),
            )
        # Record all actual spending, including an invalid upper bound; never hide overrun.
        if reply.actual_cost_micro_usd is not None and reply.actual_cost_micro_usd > row[0]:
            raise ValueError("approved_reservation_bound_exceeded")

    def summary(self):
        with closing(sqlite3.connect(self.path)) as db:
            cap = db.execute("SELECT cap FROM budget").fetchone()[0]
            spent, held, calls = db.execute(
                "SELECT COALESCE(SUM(actual),0), "
                "COALESCE(SUM(CASE WHEN actual IS NULL THEN reserve ELSE 0 END),0), "
                "COUNT(*) FROM calls"
            ).fetchone()
        return {
            "cap_micro_usd": cap,
            "spent_micro_usd": spent,
            "held_micro_usd": held,
            "attempts": calls,
        }


class CircuitBreaker:
    def __init__(self, failures=3, cooldown_seconds=60, *, clock=time.monotonic):
        if failures < 1 or cooldown_seconds <= 0:
            raise ValueError("invalid circuit configuration")
        self.limit, self.cooldown, self.clock = failures, cooldown_seconds, clock
        self.count, self.until = 0, 0.0
        self.lock = threading.Lock()

    def available(self):
        with self.lock:
            return self.clock() >= self.until

    def record(self, success):
        with self.lock:
            self.count = 0 if success else self.count + 1
            if self.count >= self.limit:
                self.until = self.clock() + self.cooldown


def cascade(
    value,
    profile,
    routing,
    gate,
    *,
    mode="local",
    backend=None,
    budget=None,
    breaker=None,
    clock=time.monotonic,
):
    start = clock()
    value, profile, routing, gate = (revalidate(v) for v in (value, profile, routing, gate))
    if mode not in {"local", "cascade"}:
        raise ValueError("only local/cascade execution belongs to this adapter")
    if profile.implementation_sha256 != implementation_hash():
        raise ValueError("verifier implementation changed; select and freeze a new profile")
    if routing.implementation_sha256 != routing_implementation_hash():
        raise ValueError("routing implementation changed; recalibrate and freeze a new policy")
    if (
        routing.verifier_profile_sha256 != digest(profile)
        or routing.fixture_only != profile.binding.fixture_only
    ):
        raise ValueError("routing/profile binding mismatch")
    if not profile.binding.fixture_only and (
        profile.status != "frozen_dev_select" or routing.status != "frozen_dev_calibrate"
    ):
        raise PermissionError("real execution requires frozen model/filter/verifier/router")
    student = verify(value, profile.config, snap=True)

    def abstain(reason, *, attempted=False, cached=False, teacher=None):
        return CascadeOutcome(
            status="abstained",
            source="none",
            reason=reason,
            student=student,
            teacher=teacher,
            external_attempted=attempted,
            cache_hit=cached,
        )

    if student.status == "answered" and student.rule_score >= routing.min_local_score:
        return CascadeOutcome(
            status="answered",
            source="student",
            answer=student.answer_after,
            reason="local_supported",
            student=student,
        )
    if mode == "local":
        return abstain("local_only")
    # Runtime/OOM errors never silently trigger a cloud substitute.
    if value.prediction.status == "error":
        return abstain("student_runtime_error")
    if value.ocr is None or value.ocr.status != "ok" or not value.ocr.spans:
        return abstain("ocr_unavailable")
    if not all(
        (
            gate.server_external_enabled,
            gate.request_allow_external,
            gate.document_may_external_process,
            gate.provider_healthy,
            gate.permission_evidence_sha256,
        )
    ):
        return abstain("external_disallowed")
    request = FallbackRequest(sample=value.sample, ocr=value.ocr, binding=profile.binding)
    key = digest(request)
    if gate.allowed_request_sha256 != key:
        return abstain("request_not_authorized")
    if gate.reserve_micro_usd <= 0:
        return abstain("budget_not_authorized")
    if (
        backend is None
        or budget is None
        or breaker is None
        or backend.profile_sha256 != profile.binding.fallback_profile_sha256
        or backend.fixture_only != profile.binding.fixture_only
    ):
        return abstain("fallback_not_configured")
    if not breaker.available():
        return abstain("provider_circuit_open")
    remaining = routing.request_timeout_seconds - (clock() - start)
    if remaining <= 0:
        return abstain("request_deadline_exceeded")
    try:
        reply = budget.begin(key, gate.reserve_micro_usd)
    except PermissionError as error:
        return abstain(str(error))
    cached = reply is not None
    if not cached:
        try:
            reply = FallbackReply.model_validate(
                backend.complete(request, timeout_seconds=remaining).model_dump()
            )
            if (
                reply.request_sha256 != key
                or reply.fixture_only != profile.binding.fixture_only
                or (reply.prediction is not None and reply.prediction.qid != value.prediction.qid)
            ):
                raise ValueError("fallback identity mismatch")
        except Exception:
            # Call may have been billed. Hold the full reserve; never log private exception text.
            reply = FallbackReply(
                request_sha256=key,
                fixture_only=profile.binding.fixture_only,
                status="provider_error",
            )
        try:
            budget.finish(reply)
        except ValueError as error:
            if str(error) != "approved_reservation_bound_exceeded":
                raise
            breaker.record(False)
            return abstain(str(error), attempted=True)
        breaker.record(reply.status == "completed")
    if clock() - start > routing.request_timeout_seconds:
        return abstain("request_deadline_exceeded", attempted=not cached, cached=cached)
    if reply.status != "completed":
        return abstain("teacher_" + reply.status, attempted=not cached, cached=cached)
    teacher_input = value.model_copy(update={"prediction": reply.prediction})
    teacher = verify(teacher_input, profile.config, snap=False)
    if teacher.status != "answered":
        return abstain(
            "teacher_verification_failed", attempted=not cached, cached=cached, teacher=teacher
        )
    return CascadeOutcome(
        status="answered",
        source="teacher",
        answer=teacher.answer_after,
        reason="teacher_verified",
        student=student,
        teacher=teacher,
        external_attempted=not cached,
        cache_hit=cached,
    )
