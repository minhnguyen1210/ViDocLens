"""Injected synthetic fallback only; no network or provider credential access."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from test_silver import HASH
from test_verifier import profile, value

from vidoclens.contracts.cascade import ExternalGate, FallbackReply, FallbackRequest
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.verification import RoutingPolicy
from vidoclens.filtering.io import digest
from vidoclens.verify.runtime import (
    BudgetCache,
    CircuitBreaker,
    cascade,
    routing_implementation_hash,
)


class Backend:
    fixture_only = True
    profile_sha256 = HASH

    def __init__(self, answer="125", *, cost=3, fail=False, advance=None):
        self.answer, self.cost, self.fail, self.advance = answer, cost, fail, advance
        self.calls = []

    def complete(self, request, *, timeout_seconds):
        self.calls.append((request, timeout_seconds))
        if self.advance:
            self.advance()
        if self.fail:
            raise TimeoutError("private provider text must not appear in outcome")
        return FallbackReply(
            request_sha256=digest(request),
            fixture_only=True,
            status="completed",
            prediction=AnswerPrediction(
                qid=request.sample.question.qid, status="answered", answer_raw=self.answer
            ),
            raw_response_sha256=HASH,
            actual_cost_micro_usd=self.cost,
        )


def setup(tmp_path, *, v=None, backend=None, cap=10):
    v, prof = v or value("124"), profile()
    policy = RoutingPolicy(
        verifier_profile_sha256=digest(prof),
        fixture_only=True,
        implementation_sha256=routing_implementation_hash(),
    )
    request = FallbackRequest(sample=v.sample, ocr=v.ocr, binding=prof.binding)
    gate = ExternalGate(
        server_external_enabled=True,
        request_allow_external=True,
        document_may_external_process=True,
        provider_healthy=True,
        permission_evidence_sha256=HASH,
        allowed_request_sha256=digest(request),
        reserve_micro_usd=5,
    )
    options = dict(
        mode="cascade",
        backend=backend or Backend(),
        budget=BudgetCache(tmp_path / "budget.sqlite", cap),
        breaker=CircuitBreaker(),
    )
    return v, prof, policy, gate, options


def test_one_verified_call_then_cache_without_new_spend(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path)
    result = cascade(v, prof, policy, gate, **opts)
    assert result.answer == "125" and result.source == "teacher"
    assert result.teacher.answer_before == "125" and result.external_attempted
    replay = cascade(v, prof, policy, gate, **opts)
    assert replay.cache_hit and not replay.external_attempted and replay.answer == "125"
    assert len(opts["backend"].calls) == 1
    assert opts["budget"].summary() == {
        "cap_micro_usd": 10,
        "spent_micro_usd": 3,
        "held_micro_usd": 0,
        "attempts": 1,
    }
    sent = opts["backend"].calls[0][0].model_dump_json()
    assert "124" not in sent and "gold" not in sent and "labels" not in sent
    assert opts["backend"].calls[0][0].max_transport_attempts == 1


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"server_external_enabled": False}, "external_disallowed"),
        ({"request_allow_external": False}, "external_disallowed"),
        ({"document_may_external_process": False}, "external_disallowed"),
        ({"provider_healthy": False}, "external_disallowed"),
        ({"permission_evidence_sha256": None}, "external_disallowed"),
        ({"allowed_request_sha256": "f" * 64}, "request_not_authorized"),
        ({"reserve_micro_usd": 0}, "budget_not_authorized"),
    ],
)
def test_each_external_gate_stops_before_call_and_cache(tmp_path, change, reason):
    v, prof, policy, gate, opts = setup(tmp_path)
    denied = gate.model_copy(update=change)
    result = cascade(v, prof, policy, denied, **opts)
    assert result.reason == reason and result.status == "abstained"
    assert not opts["backend"].calls and opts["budget"].summary()["attempts"] == 0
    cascade(v, prof, policy, gate, **opts)
    assert cascade(v, prof, policy, denied, **opts).reason == reason
    assert len(opts["backend"].calls) == 1


def test_default_local_mode_and_supported_local_never_call(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path)
    opts.pop("mode")
    assert cascade(v, prof, policy, gate, **opts).reason == "local_only"
    good = value()
    result = cascade(good, prof, policy, ExternalGate(), mode="cascade", **opts)
    assert result.source == "student" and result.answer == "125"
    assert not opts["backend"].calls


@pytest.mark.parametrize(
    "kind", ["oom", "ocr_missing", "ocr_empty", "unconfigured", "budget", "circuit"]
)
def test_operational_failure_never_silently_routes(tmp_path, kind):
    v, prof, policy, gate, opts = setup(tmp_path, cap=0 if kind == "budget" else 10)
    if kind == "oom":
        v = v.model_copy(
            update={"prediction": AnswerPrediction(qid=v.prediction.qid, status="error")}
        )
    elif kind == "ocr_missing":
        v = v.model_copy(update={"ocr": None})
    elif kind == "ocr_empty":
        v = value("124", [])
    elif kind == "unconfigured":
        opts["backend"] = None
    elif kind == "circuit":
        for _ in range(3):
            opts["breaker"].record(False)
    result = cascade(v, prof, policy, gate, **opts)
    assert result.status == "abstained" and not result.external_attempted
    assert opts["budget"].summary()["attempts"] == 0


def test_teacher_wrong_field_is_rejected_without_second_fallback(tmp_path):
    v = value("124", ["Tổng tiền 125", "Khách đưa 200"])
    v, prof, policy, gate, opts = setup(tmp_path, v=v, backend=Backend("200"))
    result = cascade(v, prof, policy, gate, **opts)
    assert result.reason == "teacher_verification_failed"
    assert result.teacher.reason == "wrong_field_risk" and result.answer is None
    assert len(opts["backend"].calls) == 1


def test_timeout_holds_unknown_cost_and_replays_failure(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path, backend=Backend(fail=True))
    result = cascade(v, prof, policy, gate, **opts)
    assert result.reason == "teacher_provider_error" and "private" not in result.model_dump_json()
    assert opts["budget"].summary()["held_micro_usd"] == 5
    assert cascade(v, prof, policy, gate, **opts).cache_hit
    assert len(opts["backend"].calls) == 1


def test_deadline_discards_late_result_and_records_cost(tmp_path):
    now = [10.0]
    backend = Backend(advance=lambda: now.__setitem__(0, 56.0))
    v, prof, policy, gate, opts = setup(tmp_path, backend=backend)
    opts["clock"] = lambda: now[0]
    result = cascade(v, prof, policy, gate, **opts)
    assert result.reason == "request_deadline_exceeded" and result.external_attempted
    assert backend.calls[0][1] == 45
    assert opts["budget"].summary()["spent_micro_usd"] == 3


def test_reservation_overrun_not_hidden_or_replayed_as_answer(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path, backend=Backend(cost=12))
    assert cascade(v, prof, policy, gate, **opts).reason == "approved_reservation_bound_exceeded"
    assert opts["budget"].summary()["spent_micro_usd"] == 12
    replay = cascade(v, prof, policy, gate, **opts)
    assert replay.status == "abstained" and replay.reason == "teacher_provider_error"
    assert len(opts["backend"].calls) == 1


def test_invalid_identity_holds_reserve_without_answer(tmp_path):
    class Wrong(Backend):
        def complete(self, request, **kwargs):
            return super().complete(request, **kwargs).model_copy(update={"request_sha256": HASH})

    v, prof, policy, gate, opts = setup(tmp_path, backend=Wrong())
    assert cascade(v, prof, policy, gate, **opts).status == "abstained"
    assert opts["budget"].summary()["held_micro_usd"] == 5


def test_budget_atomic_concurrency_crash_hold_and_corruption(tmp_path):
    db = BudgetCache(tmp_path / "budget.sqlite", 5)

    def reserve(key):
        try:
            db.begin(key, 5)
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, [HASH, "b" * 64]))
    assert sum(results) == 1 and db.summary()["held_micro_usd"] == 5
    key = HASH if results[0] else "b" * 64
    with pytest.raises(PermissionError, match="inflight_or_uncertain"):
        db.begin(key, 5)
    reply = FallbackReply(request_sha256=key, fixture_only=True, status="timeout")
    db.finish(reply)
    with pytest.raises(ValueError, match="immutable"):
        BudgetCache(db.path, 6)
    with sqlite3.connect(db.path) as connection:
        connection.execute("UPDATE calls SET checksum=? WHERE key=?", ("c" * 64, key))
    with pytest.raises(ValueError, match="corrupted"):
        db.begin(key, 5)


def test_circuit_recovers_and_success_resets():
    now = [0]
    breaker = CircuitBreaker(failures=2, cooldown_seconds=10, clock=lambda: now[0])
    breaker.record(False)
    assert breaker.available()
    breaker.record(False)
    assert not breaker.available()
    now[0] = 10
    assert breaker.available()
    breaker.record(True)
    breaker.record(False)
    assert breaker.available()


def test_real_execution_requires_frozen_profile_and_no_fixture_confusion(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path)
    real = prof.model_copy(
        update={"binding": prof.binding.model_copy(update={"fixture_only": False})}
    )
    policy = policy.model_copy(
        update={"fixture_only": False, "verifier_profile_sha256": digest(real)}
    )
    with pytest.raises(PermissionError, match="frozen"):
        cascade(v, real, policy, gate, **opts)
    with pytest.raises(ValidationError):
        ExternalGate(request_allow_external="true")


def test_changed_routing_code_cannot_reuse_frozen_policy(tmp_path):
    v, prof, policy, gate, opts = setup(tmp_path)
    changed = policy.model_copy(update={"implementation_sha256": HASH})
    with pytest.raises(ValueError, match="routing implementation changed"):
        cascade(v, prof, changed, gate, **opts)
    assert not opts["backend"].calls
