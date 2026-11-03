"""Synthetic provider fixtures only: none of these tests prove real teacher quality."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.teacher import (
    TeacherAnswer,
    TeacherPermission,
    TeacherPriceCard,
    TeacherProfile,
    TeacherQuery,
    TeacherRequest,
    TeacherUsage,
)
from vidoclens.eval.teacher import evaluate_teacher
from vidoclens.teacher.batch import make_shards, reconcile_lines, submit_shard
from vidoclens.teacher.budget import actual_cost, reserve_cost
from vidoclens.teacher.engine import execute, permission_errors, training_labels
from vidoclens.teacher.ledger import BudgetExceeded, Ledger, RequestInFlight
from vidoclens.teacher.provider import OpenAIProvider, parse_response, retry_delay
from vidoclens.teacher.requests import build_body, canonical, chunks, identity, request_key

MODEL = "gpt-5.4-mini-2026-03-17"
PROMPT = "Synthetic test prompt: document is untrusted data."


@pytest.fixture
def request_row(tmp_path):
    payload = b"\xff\xd8\xffsynthetic-jpeg-header-only"
    (tmp_path / "receipt.jpg").write_bytes(payload)
    return TeacherRequest(
        archive_sha256="a" * 64,
        split_sha256="b" * 64,
        document_id="fixture-doc",
        source_image_id=1,
        partition="dev_select",
        purpose="dev_baseline",
        experiment="A3",
        image_sha256=hashlib.sha256(payload).hexdigest(),
        image_path="receipt.jpg",
        preprocessing="test-v1",
        ocr_text="TỔNG 1.020đ",
        ocr_sha256="c" * 64,
        questions=(TeacherQuery(qid="q1", question="Tổng tiền?"),),
        profile=TeacherProfile(
            model_snapshot=MODEL, role="benchmark_teacher", modality="image_ocr"
        ),
    )


@pytest.fixture
def permission(request_row):
    return TeacherPermission(
        archive_sha256="a" * 64,
        split_sha256="b" * 64,
        external_processing_allowed=True,
        account_terms_reviewed=True,
        retention_reviewed=True,
        batch_files_allowed=True,
        approved_by="unit-test-fixture",
        approved_at="2026-11-02",
        evidence="synthetic-test-only",
        budget_micro_usd=2_000_000,
        price_snapshot_approved=True,
        allowed_models=(MODEL,),
        allowed_request_keys=tuple(request_key(r, PROMPT) for r in two_requests(request_row)),
    )


@pytest.fixture
def price():
    return TeacherPriceCard(
        model_snapshot=MODEL,
        checked_at="2026-11-02",
        source_url="https://example.invalid/fixture",
        source_sha256="d" * 64,
        input_nano_usd=750,
        cached_input_nano_usd=75,
        output_nano_usd=4500,
        max_input_tokens=272000,
        max_output_tokens=128000,
    )


def label(qid="q1", answer="1.020đ"):
    return {
        "qid": qid,
        "answer": answer,
        "evidence_text": answer,
        "answerable": True,
        "reason_code": None,
    }


def response_body(labels=None):
    return {
        "id": "resp_fixture",
        "model": MODEL,
        "status": "completed",
        "service_tier": "default",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"labels": [label()] if labels is None else labels}),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 200},
            "output_tokens": 100,
            "total_tokens": 1100,
        },
    }


def invoke(tmp_path, request_row, permission, price, handler, **kwargs):
    ledger = Ledger(tmp_path / "ledger.sqlite", permission.budget_micro_usd)
    provider = OpenAIProvider("synthetic-not-a-secret", transport=httpx.MockTransport(handler))
    try:
        result = execute(
            request_row,
            PROMPT,
            root=tmp_path,
            permission=permission,
            price=price,
            ledger=ledger,
            provider=provider,
            sleep=lambda _: None,
            jitter=lambda: 0,
            **kwargs,
        )
    finally:
        provider.close()
    return result, ledger


def test_request_rejects_gold_and_test_partition(request_row):
    for addition in (
        {"answer": "secret-gold"},
        {"partition": "test"},
        {"questions": [{"qid": "q", "question": "x", "answer": "gold"}]},
    ):
        with pytest.raises(ValidationError):
            TeacherRequest.model_validate(request_row.model_dump() | addition)


def test_deterministic_chunks_preserve_all_questions():
    questions = [TeacherQuery(qid=str(i), question="Số tiền?") for i in range(19)]
    first = tuple(chunks(questions, max_questions=8))
    assert [len(g) for g in first] == [8, 8, 3]
    assert first == tuple(chunks(questions, max_questions=8))
    assert [q for group in first for q in group] == questions
    with pytest.raises(ValueError):
        tuple(chunks([questions[0], questions[0]]))
    with pytest.raises(ValueError):
        tuple(chunks(questions, max_utf8_bytes=1))


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_sha256", "e" * 64),
        ("ocr_sha256", "f" * 64),
        ("ocr_text", "TỔNG 1.021đ"),
        ("preprocessing", "changed"),
        ("split_sha256", "e" * 64),
    ],
)
def test_cache_identity_covers_input(request_row, field, value):
    changed = TeacherRequest.model_validate(request_row.model_dump() | {field: value})
    assert request_key(changed, PROMPT) != request_key(request_row, PROMPT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_snapshot", "gpt-5.4-2026-03-05"),
        ("max_output_tokens", 2000),
        ("image_detail", "low"),
    ],
)
def test_cache_identity_covers_profile(request_row, field, value):
    profile = TeacherProfile.model_validate(request_row.profile.model_dump() | {field: value})
    changed = TeacherRequest.model_validate(request_row.model_dump() | {"profile": profile})
    assert request_key(changed, PROMPT) != request_key(request_row, PROMPT)
    assert request_key(request_row, PROMPT + "x") != request_key(request_row, PROMPT)


def test_key_order_and_path_policy(request_row):
    questions = [*request_row.questions, TeacherQuery(qid="q2", question="Ngày?")]
    a = TeacherRequest.model_validate(request_row.model_dump() | {"questions": questions})
    b = TeacherRequest.model_validate(a.model_dump() | {"questions": list(reversed(questions))})
    assert request_key(a, PROMPT) != request_key(b, PROMPT)
    moved = TeacherRequest.model_validate(a.model_dump() | {"image_path": "elsewhere.jpg"})
    assert request_key(a, PROMPT) == request_key(moved, PROMPT)


def test_payload_modalities_no_gold_or_tools(tmp_path, request_row):
    image = TeacherRequest.model_validate(
        request_row.model_dump()
        | {
            "ocr_text": None,
            "ocr_sha256": None,
            "profile": request_row.profile.model_dump() | {"modality": "image"},
        }
    )
    body = build_body(image, PROMPT, tmp_path)
    assert body["store"] is False and "tools" not in body
    assert body["text"]["format"]["strict"] is True
    assert "ocr_text" not in json.loads(body["input"][0]["content"][0]["text"])
    assert body["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")
    text_only = TeacherRequest.model_validate(
        request_row.model_dump()
        | {
            "profile": request_row.profile.model_dump() | {"modality": "ocr_text"},
        }
    )
    assert len(build_body(text_only, PROMPT, tmp_path)["input"][0]["content"]) == 1
    (tmp_path / "receipt.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="image bytes"):
        build_body(request_row, PROMPT, tmp_path)


def test_output_preserves_digits_diacritics_and_newlines(request_row):
    raw = "Cà phê\n1.020đ"
    result = parse_response(
        response_body([label(answer=raw)]), request_row, request_key(request_row, PROMPT)
    )
    assert result.status == "ok" and result.labels[0].answer == raw


@pytest.mark.parametrize("labels", [[], [label(), label()], [label("unknown")]])
def test_exact_qid_coverage(request_row, labels):
    result = parse_response(response_body(labels), request_row, request_key(request_row, PROMPT))
    assert result.status == "qid_error" and not result.labels


@pytest.mark.parametrize(
    "change",
    [
        {"answerable": "true"},
        {"answerable": False},
        {"answer": " "},
        {"reason_code": "guessed"},
        {"confidence": 1},
    ],
)
def test_strict_answer_states(change):
    with pytest.raises(ValidationError):
        TeacherAnswer.model_validate(label() | change)


@pytest.mark.parametrize(
    "case,status",
    [
        ("refusal", "refused"),
        ("incomplete", "incomplete"),
        ("invalid_json", "schema_error"),
        ("missing_usage", "usage_error"),
        ("bad_usage", "usage_error"),
        ("wrong_model", "model_mismatch"),
        ("tool_output", "schema_error"),
    ],
)
def test_provider_error_states(request_row, case, status):
    body = response_body()
    if case == "refusal":
        body["output"][0]["content"] = [{"type": "refusal", "refusal": "fixture"}]
    elif case == "incomplete":
        body["status"] = "incomplete"
    elif case == "invalid_json":
        body["output"][0]["content"][0]["text"] = "broken-json"
    elif case == "missing_usage":
        body.pop("usage")
    elif case == "bad_usage":
        body["usage"]["input_tokens"] = True
    elif case == "wrong_model":
        body["model"] = "another-model"
    else:
        body["output"] = [{"type": "function_call"}]
    result = parse_response(body, request_row, request_key(request_row, PROMPT))
    assert result.status == status and not result.labels


def test_budget_rounding_cached_tokens_and_batch(request_row, price):
    usage = TeacherUsage(
        input_tokens=1000, cached_input_tokens=200, output_tokens=100, total_tokens=1100
    )
    assert actual_cost(usage, price) == 1065
    assert actual_cost(usage, price, batch=True) == 533
    assert reserve_cost(request_row.profile, price) == 222432
    assert actual_cost(usage, price) <= reserve_cost(request_row.profile, price)


def test_long_context_uses_full_tier(price):
    card = TeacherPriceCard.model_validate(
        price.model_dump()
        | {
            "input_nano_usd": 2500,
            "cached_input_nano_usd": 250,
            "output_nano_usd": 15000,
            "long_context_threshold": 272000,
            "long_input_multiplier": 2,
            "long_output_multiplier_milli": 1500,
        }
    )
    below = TeacherUsage(input_tokens=272000, output_tokens=100, total_tokens=272100)
    above = TeacherUsage(input_tokens=272001, output_tokens=100, total_tokens=272101)
    assert actual_cost(below, card) == 681500
    assert actual_cost(above, card) == 1362255


def test_denied_permission_makes_zero_calls(tmp_path, request_row, permission, price):
    calls = []
    denied = permission.model_copy(
        update={"external_processing_allowed": False, "budget_micro_usd": 0}
    )
    with pytest.raises(PermissionError):
        invoke(tmp_path, request_row, denied, price, lambda r: calls.append(r))
    assert not calls
    assert "positive_budget" in permission_errors(request_row, denied)


def test_live_shape_cache_replay_zero_calls(tmp_path, request_row, permission, price):
    calls = []

    def handler(req):
        calls.append(req)
        assert str(req.url) == "https://api.openai.com/v1/responses"
        assert json.loads(req.content)["text"]["format"]["type"] == "json_schema"
        return httpx.Response(200, json=response_body())

    (first, hit), ledger = invoke(tmp_path, request_row, permission, price, handler)
    (second, second_hit), _ = invoke(tmp_path, request_row, permission, price, handler)
    assert first == second and not hit and second_hit and len(calls) == 1
    assert ledger.summary()["spent_micro_usd"] == 1065
    assert ledger.summary()["reserved_micro_usd"] == 0
    with pytest.raises(PermissionError):
        training_labels(request_row, first, permission, PROMPT)


def test_failed_cache_never_becomes_success(tmp_path, request_row, permission, price):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=response_body([]))

    (first, _), _ = invoke(tmp_path, request_row, permission, price, handler)
    (second, hit), _ = invoke(tmp_path, request_row, permission, price, handler)
    assert first.status == second.status == "qid_error" and hit and len(calls) == 1


@pytest.mark.parametrize(
    "status,attempts,uncertain", [(401, 1, 0), (400, 1, 0), (429, 3, 0), (503, 3, 3)]
)
def test_http_retry_accounting(
    tmp_path, request_row, permission, price, status, attempts, uncertain
):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(status, json={"error": {"code": "fixture"}})

    (result, _), ledger = invoke(tmp_path, request_row, permission, price, handler)
    assert len(calls) == attempts and result.status == "provider_error"
    assert ledger.summary()["uncertain_micro_usd"] == uncertain * reserve_cost(
        request_row.profile, price
    )


def test_timeout_then_success_retains_unknown_charge(tmp_path, request_row, permission, price):
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            raise httpx.ReadTimeout("synthetic", request=req)
        return httpx.Response(200, json=response_body())

    (result, _), ledger = invoke(tmp_path, request_row, permission, price, handler)
    assert result.status == "ok" and len(calls) == 2
    assert ledger.summary()["uncertain_micro_usd"] == reserve_cost(request_row.profile, price)


def test_retry_stops_before_exceeding_budget(tmp_path, request_row, permission, price):
    cap = reserve_cost(request_row.profile, price)
    grant = permission.model_copy(update={"budget_micro_usd": cap})
    calls = []

    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout("synthetic", request=req)

    (result, _), ledger = invoke(tmp_path, request_row, grant, price, handler)
    assert len(calls) == 1 and result.error_code == "retry_budget_exhausted"
    assert ledger.summary()["committed_micro_usd"] == cap


def test_retry_after_is_not_clamped_early(tmp_path, request_row, permission, price):
    assert retry_delay("120", 0, 0) == 120
    now = datetime(2026, 11, 2, tzinfo=UTC)
    assert retry_delay("Mon, 02 Nov 2026 00:02:00 GMT", 0, 0, now=now) == 120
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(429, headers={"Retry-After": "120"}, json={})

    invoke(tmp_path, request_row, permission, price, handler)
    assert len(calls) == 1


def test_ledger_concurrency_and_crash_holds(tmp_path, request_row):
    path = tmp_path / "concurrent.sqlite"
    ledger = Ledger(path, 100)

    def reserve(index):
        data = {"fixture": index}
        from vidoclens.teacher.requests import digest

        try:
            return Ledger(path, 100).start(digest(data), data, 70)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = list(pool.map(reserve, range(4)))
    assert len([x for x in attempts if x]) == 1
    assert ledger.summary()["reserved_micro_usd"] == 70
    unresolved = ledger.unresolved()[0]
    with pytest.raises(RequestInFlight):
        ledger.cached(unresolved["key"])
    with pytest.raises(ValueError):
        ledger.reconcile_charge(unresolved["id"], 0, "")
    ledger.reconcile_charge(unresolved["id"], 0, "fixture provider accounting: not charged")
    assert ledger.summary()["committed_micro_usd"] == 0
    with pytest.raises(ValueError):
        Ledger(path, 200)


def test_batch_atomic_reservation_rolls_back(tmp_path):
    from vidoclens.teacher.requests import digest

    ledger = Ledger(tmp_path / "batch.sqlite", 100)
    entries = [(digest({"n": i}), {"n": i}, 60) for i in range(2)]
    with pytest.raises(BudgetExceeded):
        ledger.start_many(entries)
    assert ledger.summary()["attempts"] == 0


def two_requests(request_row):
    return [
        request_row,
        TeacherRequest.model_validate(
            request_row.model_dump()
            | {
                "questions": [{"qid": "q2", "question": "Ngày?"}],
            }
        ),
    ]


def test_batch_shards_bytes_tokens_and_model(tmp_path, request_row, price):
    rows = two_requests(request_row)
    prices = {MODEL: price}
    shards = list(make_shards(rows, PROMPT, tmp_path, prices, max_input_tokens=300000))
    assert [len(s) for s in shards] == [1, 1]
    size = len(shards[0][0][2])
    assert len(list(make_shards(rows, PROMPT, tmp_path, prices, max_bytes=size + 2))) == 2
    with pytest.raises(ValueError):
        list(make_shards(rows, PROMPT, tmp_path, prices, max_bytes=10))
    with pytest.raises(ValueError):
        list(make_shards([rows[0], rows[0]], PROMPT, tmp_path, prices))


def batch_ledger(tmp_path, rows, price):
    ledger = Ledger(tmp_path / "batch.sqlite", 2_000_000)
    attempts = ledger.start_many(
        [
            (
                request_key(r, PROMPT),
                identity(r, PROMPT),
                reserve_cost(r.profile, price, batch=True),
            )
            for r in rows
        ]
    )
    return ledger, attempts


def test_batch_reconcile_unordered_expired_and_resubmit(tmp_path, request_row, price):
    rows = two_requests(request_row)
    ledger, attempts = batch_ledger(tmp_path, rows, price)
    first, second = [request_key(r, PROMPT) for r in rows]
    output = canonical(
        {
            "custom_id": second,
            "response": {"status_code": 200, "body": response_body([label("q2")])},
            "error": None,
        }
    )
    errors = canonical({"custom_id": first, "response": None, "error": {"code": "batch_expired"}})
    report = reconcile_lines(
        rows,
        PROMPT,
        batch_state="expired",
        output=output,
        errors=errors,
        prices={MODEL: price},
        ledger=ledger,
        attempts=attempts,
    )
    assert report["successful"] == [second] and report["resubmit_eligible"] == [first]
    assert ledger.summary()["spent_micro_usd"] == 533
    ledger.allow_batch_resubmit(first)
    assert ledger.cached(first) is None
    with pytest.raises(ValueError):
        ledger.allow_batch_resubmit(second)


def test_batch_missing_unknown_is_never_auto_released(tmp_path, request_row, price):
    ledger, attempts = batch_ledger(tmp_path, [request_row], price)
    report = reconcile_lines(
        [request_row],
        PROMPT,
        batch_state="expired",
        output="",
        errors="",
        prices={MODEL: price},
        ledger=ledger,
        attempts=attempts,
    )
    key = request_key(request_row, PROMPT)
    assert report["missing_uncertain"] == [key] and not report["resubmit_eligible"]
    assert ledger.summary()["uncertain_micro_usd"] > 0
    with pytest.raises(ValueError):
        ledger.allow_batch_resubmit(key)


@pytest.mark.parametrize("kind", ["duplicate", "unknown", "nonterminal"])
def test_invalid_batch_leaves_reservations_intact(tmp_path, request_row, price, kind):
    ledger, attempts = batch_ledger(tmp_path, [request_row], price)
    key = request_key(request_row, PROMPT)
    row = canonical(
        {"custom_id": "wrong" if kind == "unknown" else key, "error": {"code": "batch_expired"}}
    )
    with pytest.raises(ValueError):
        reconcile_lines(
            [request_row],
            PROMPT,
            batch_state="in_progress" if kind == "nonterminal" else "expired",
            output=row + "\n" + row if kind == "duplicate" else row,
            errors="",
            prices={MODEL: price},
            ledger=ledger,
            attempts=attempts,
        )
    assert ledger.summary()["reserved_micro_usd"] > 0
    assert ledger.summary()["attempts"] == 1


def test_batch_upload_is_gated_and_reserved_before_http(tmp_path, request_row, permission, price):
    ledger = Ledger(tmp_path / "batch.sqlite", permission.budget_micro_usd)
    shard = list(make_shards([request_row], PROMPT, tmp_path, {MODEL: price}))[0]
    calls = []

    def handler(req):
        calls.append(req)
        assert ledger.summary()["reserved_micro_usd"] > 0
        return httpx.Response(
            200, json={"id": "file-fixture" if len(calls) == 1 else "batch_fixture"}
        )

    provider = OpenAIProvider("synthetic", transport=httpx.MockTransport(handler))
    try:
        batch_id, _ = submit_shard(
            shard,
            PROMPT,
            permission,
            {MODEL: price},
            ledger,
            provider,
            tmp_path / "journal.jsonl",
            tmp_path,
        )
        assert batch_id == "batch_fixture" and len(calls) == 2
        with pytest.raises(ValueError):
            submit_shard(
                shard,
                PROMPT,
                permission,
                {MODEL: price},
                ledger,
                provider,
                tmp_path / "journal.jsonl",
                tmp_path,
            )
    finally:
        provider.close()


def test_evaluation_all_questions_including_errors_and_missing(request_row):
    rows = two_requests(request_row)
    third = TeacherRequest.model_validate(
        request_row.model_dump()
        | {
            "questions": [{"qid": "q3", "question": "Số?"}],
        }
    )
    rows.append(third)
    results = [
        parse_response(response_body(), rows[0], request_key(rows[0], PROMPT)),
        parse_response(response_body([]), rows[1], request_key(rows[1], PROMPT)),
    ]
    refs = [
        GoldReference(qid=f"q{i}", document_id="fixture-doc", answers=("1.020đ",))
        for i in (1, 2, 3)
    ]
    report = evaluate_teacher(rows, results, refs, PROMPT)["metrics"]["A3"]
    assert report["strict"]["strict_nfc_em"] == pytest.approx(1 / 3)
    assert report["strict"]["n_error"] == report["strict"]["n_missing"] == 1
    assert report["compatible"]["accuracy"] == pytest.approx(1 / 3)


def test_cache_rejects_changed_image_bytes(tmp_path, request_row, permission, price):
    invoke(
        tmp_path,
        request_row,
        permission,
        price,
        lambda r: httpx.Response(200, json=response_body()),
    )
    (tmp_path / "receipt.jpg").write_bytes(b"changed after first run")
    with pytest.raises(ValueError, match="image bytes"):
        invoke(
            tmp_path,
            request_row,
            permission,
            price,
            lambda r: pytest.fail("cache validation must not call provider"),
        )


def test_corrupt_cache_and_spend_overrun_are_not_hidden(tmp_path, request_row, permission, price):
    import sqlite3

    (result, _), ledger = invoke(
        tmp_path,
        request_row,
        permission,
        price,
        lambda r: httpx.Response(200, json=response_body()),
    )
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE requests SET raw='{}'")
    with pytest.raises(ValueError, match="checksum"):
        ledger.cached(result.request_key)
    from vidoclens.teacher.requests import digest

    small = Ledger(tmp_path / "overrun.sqlite", 100)
    data = {"fixture": "overrun"}
    attempt = small.start(digest(data), data, 50)
    small.settle(attempt, 101, "synthetic provider usage over estimate")
    assert small.summary()["over_cap"] and small.summary()["spent_micro_usd"] == 101
    with pytest.raises(BudgetExceeded):
        small.start(digest({"n": 2}), {"n": 2}, 1)


def test_incomplete_unknown_model_cost_remains_uncertain(tmp_path, request_row, permission, price):
    body = response_body() | {"status": "incomplete", "model": "not-priced"}
    (result, _), ledger = invoke(
        tmp_path, request_row, permission, price, lambda r: httpx.Response(200, json=body)
    )
    assert result.status == "incomplete"
    assert ledger.summary()["spent_micro_usd"] == 0
    assert ledger.summary()["uncertain_micro_usd"] == reserve_cost(request_row.profile, price)


def test_batch_reconcile_idempotent(tmp_path, request_row, price):
    ledger, attempts = batch_ledger(tmp_path, [request_row], price)
    output = canonical(
        {
            "custom_id": request_key(request_row, PROMPT),
            "response": {"status_code": 200, "body": response_body()},
        }
    )
    args = dict(
        batch_state="completed",
        output=output,
        errors="",
        prices={MODEL: price},
        ledger=ledger,
        attempts=attempts,
    )
    first = reconcile_lines([request_row], PROMPT, **args)
    second = reconcile_lines([request_row], PROMPT, **args)
    assert first == second and ledger.summary()["attempts"] == 1


def test_batch_tampered_body_blocked_before_submit(tmp_path, request_row, permission, price):
    ledger = Ledger(tmp_path / "batch.sqlite", permission.budget_micro_usd)
    shard = list(make_shards([request_row], PROMPT, tmp_path, {MODEL: price}))[0]
    req, key, encoded = shard[0]
    row = json.loads(encoded)
    row["body"]["instructions"] = "unauthorized prompt"
    altered = [(req, key, (canonical(row) + "\n").encode())]
    with pytest.raises(ValueError):
        submit_shard(
            altered,
            PROMPT,
            permission,
            {MODEL: price},
            ledger,
            None,
            tmp_path / "journal.jsonl",
            tmp_path,
        )
    assert ledger.summary()["attempts"] == 0


def test_cli_permission_gate_precedes_credentials_and_output(tmp_path, request_row, monkeypatch):
    from typer.testing import CliRunner

    from vidoclens.cli import app
    from vidoclens.teacher import cli

    grant = TeacherPermission(archive_sha256="a" * 64, split_sha256="b" * 64)
    monkeypatch.setattr(cli, "read_plan", lambda *args: ([request_row], PROMPT, {}))
    monkeypatch.setattr(cli, "settings", lambda *args: ({}, grant, {}))
    monkeypatch.setattr(
        cli, "OpenAIProvider", lambda *a, **kw: pytest.fail("must not read credentials")
    )
    output = tmp_path / "denied"
    result = CliRunner().invoke(
        app, ["teacher", "run", "unused-plan", str(output), "--experiment", "A3"]
    )
    assert isinstance(result.exception, PermissionError) and not output.exists()


def test_ocr_selection_dev_components_never_touches_test():
    from types import SimpleNamespace

    from vidoclens.ocr.quality import select_pilot

    images = [SimpleNamespace(source_image_id=i) for i in range(4)]
    plan = SimpleNamespace(
        assignments=[
            SimpleNamespace(
                source_image_id=0,
                partition="dev_select",
                gold_for_training=False,
                duplicate_group_id="g0",
            ),
            SimpleNamespace(
                source_image_id=1,
                partition="dev_select",
                gold_for_training=False,
                duplicate_group_id="g0",
            ),
            SimpleNamespace(
                source_image_id=2,
                partition="dev_select",
                gold_for_training=False,
                duplicate_group_id="g2",
            ),
            SimpleNamespace(
                source_image_id=3,
                partition="test",
                gold_for_training=False,
                duplicate_group_id="g3",
            ),
        ]
    )
    selected = select_pilot(images, plan, count=2, partition="dev_select")
    assert {r.source_image_id for r in selected} == {0, 2}
    with pytest.raises(ValueError):
        select_pilot(images, plan, count=1, partition="test")


def test_exact_request_grant_does_not_extend_to_new_prompt(request_row, permission):
    assert permission_errors(request_row, permission, prompt=PROMPT) == []
    assert "request_scope_permission" in permission_errors(
        request_row, permission, prompt=PROMPT + "changed"
    )
    assert "batch_files_allowed" in permission_errors(
        request_row,
        permission.model_copy(update={"batch_files_allowed": False}),
        prompt=PROMPT,
        batch=True,
    )


def test_batch_attempt_mapping_checked_before_changes(tmp_path, request_row, price):
    rows = two_requests(request_row)
    ledger, attempts = batch_ledger(tmp_path, rows, price)
    keys = list(attempts)
    wrong = {keys[0]: attempts[keys[1]], keys[1]: attempts[keys[0]]}
    before = ledger.summary()
    with pytest.raises(ValueError, match="mapping"):
        reconcile_lines(
            rows,
            PROMPT,
            batch_state="expired",
            output="",
            errors="",
            prices={MODEL: price},
            ledger=ledger,
            attempts=wrong,
        )
    assert ledger.summary() == before


def test_cli_stops_campaign_on_auth_error(tmp_path, request_row, permission, price, monkeypatch):
    from typer.testing import CliRunner

    from vidoclens.cli import app
    from vidoclens.common.pilot import write_json
    from vidoclens.teacher import cli

    rows = two_requests(request_row)
    (tmp_path / "plan").mkdir()
    write_json(tmp_path / "plan/manifest.json", {"fixture": True})
    write_json(tmp_path / "approval.json", permission.model_dump(mode="json"))
    cfg = {
        "ledger_path": "ledger.sqlite",
        "timeout_seconds": 60,
        "max_retries": 2,
        "permission_path": "approval.json",
    }
    monkeypatch.setattr(cli, "read_plan", lambda *args: (rows, PROMPT, {}))
    monkeypatch.setattr(cli, "settings", lambda *args: (cfg, permission, {MODEL: price}))
    monkeypatch.setattr(cli, "validate_frozen_inputs", lambda *args: None)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-secret")
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(401, json={"error": {"code": "fixture_auth_error"}})

    monkeypatch.setattr(
        cli,
        "OpenAIProvider",
        lambda *a, **kw: OpenAIProvider(
            "synthetic-not-a-secret",
            transport=httpx.MockTransport(handler),
        ),
    )
    result = CliRunner().invoke(
        app, ["teacher", "run", "plan", "run", "--experiment", "A3", "--root", str(tmp_path)]
    )
    assert result.exit_code != 0 and len(calls) == 1
    report = json.loads((tmp_path / "run/run.json").read_text(encoding="utf-8"))
    assert not report["complete"] and report["completed"] == 1
    assert report["ledger"]["spent_micro_usd"] == 0


def test_authentication_error_message_is_not_cached(tmp_path, request_row, permission, price):
    import sqlite3

    marker = "synthetic-credential-fragment-never-store"
    (_, _), ledger = invoke(
        tmp_path,
        request_row,
        permission,
        price,
        lambda r: httpx.Response(
            401,
            json={"error": {"message": marker}},
        ),
    )
    with sqlite3.connect(ledger.path) as db:
        final = db.execute("SELECT raw FROM requests").fetchone()[0]
        attempt = db.execute("SELECT raw FROM attempts").fetchone()[0]
    assert marker not in final and marker not in attempt
    assert json.loads(final)["authentication_message_omitted"] is True
