"""Synthetic offline fixtures. These checks do not measure teacher/student quality."""

import json
import unicodedata

import pytest
from pydantic import ValidationError

from vidoclens.contracts.dataset import GoldReference, ReceiptQuestion
from vidoclens.contracts.models import Box, OCRResult, OCRSpan
from vidoclens.contracts.silver import (
    FilterConfig,
    SilverApproval,
    SilverBatch,
    SilverLabel,
    SilverPool,
    SilverSample,
)
from vidoclens.eval.silver import audit_filter
from vidoclens.filtering.bundle import load_bundle, write_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest
from vidoclens.filtering.matching import Candidate, match_part, normalize
from vidoclens.filtering.pipeline import filter_batch, summarize

HASH = "a" * 64


def sample(index, *, source="train", question="Tổng tiền?", image_id=None):
    image_id = index if image_id is None else image_id
    doc = f"receiptvqa:{HASH}:image:{image_id}"
    q = ReceiptQuestion(
        archive_sha256=HASH,
        source_split=source,
        source_image_id=image_id,
        source_question_id=index,
        source_row_index=index,
        filename=f"{image_id}.png",
        document_id=doc,
        qid=f"{doc}:question:{index}",
        question_raw=question,
        question_nfc=unicodedata.normalize("NFC", question),
    )
    return SilverSample(question=q, duplicate_group_id=f"g{image_id}", image_sha256=HASH)


def pool(count=1, partition="train_fit"):
    source = "dev" if partition == "dev_select" else "train"
    return SilverPool(
        partition=partition,
        archive_sha256=HASH,
        access_plan_sha256=HASH,
        inventory_sha256=HASH,
        samples=tuple(sample(i, source=source) for i in range(1, count + 1)),
        gold_samples=(sample(100),) if partition == "train_fit" else (),
    )


def batch(p, answers, *, protocol="whole_answer_v1"):
    return SilverBatch(
        fixture_only=True,
        pool_sha256=digest(p),
        run_id="synthetic",
        model_id="synthetic/local",
        model_revision="b" * 40,
        prompt_sha256=HASH,
        generation_config_sha256=HASH,
        environment_sha256=HASH,
        part_protocol=protocol,
        labels=tuple(
            SilverLabel(
                qid=s.question.qid,
                status="answered" if a is not None else "unanswerable",
                answer_raw=a,
                reason=None if a is not None else "unreadable",
                raw_response_sha256=HASH,
            )
            for s, a in zip(p.samples, answers, strict=True)
        ),
    )


def ocr(s, lines):
    return OCRResult(
        document_id=s.question.document_id,
        image_sha256=s.image_sha256,
        engine="synthetic",
        engine_revision="1",
        preprocessing_hash=HASH,
        status="ok" if lines else "empty",
        spans=[
            OCRSpan(
                span_id=f"l{i}",
                line_id=f"l{i}",
                reading_order=i,
                text_raw=text,
                text_nfc=unicodedata.normalize("NFC", text),
                box=Box(x0=0, y0=0, x1=1, y1=1),
            )
            for i, text in enumerate(lines)
        ],
    )


def frozen():
    return FilterConfig(
        status="frozen_dev_select",
        freeze_evidence_sha256=HASH,
        freeze_access_plan_sha256=HASH,
        freeze_fixture_only=True,
    )


def approve(p, b):
    return SilverApproval(
        pool_sha256=digest(p),
        batch_sha256=digest(b),
        approved_by="synthetic-test-only",
        evidence_sha256=HASH,
        training_labels_allowed=True,
        data_rights_verified=True,
        model_license_verified=True,
        quality_pilot_passed=True,
    )


@pytest.mark.parametrize(
    "answer,line,keep",
    [
        ("12", "125.000", False),
        ("1,5", "15", False),
        ("-12", "12", False),
        ("12", "- 12", False),
        ("12", "− 12", False),
        ("12", "( 12 )", False),
        ("12", "12 €", False),
        ("12", "12 kg", False),
        ("125.000", "125.000 đ", False),
        ("125.000 đ", "Tổng: 125.000 đ", True),
        ("007", "7", False),
        ("007", "Mã 007", True),
        ("12", "12 / 05 / 2026", False),
        ("1,5", "Số lượng 1,5", True),
        ("AB12", "AB13", False),
        ("Cửa hàng", "Cua hang", False),
        ("AB", "AC", False),
        ("abcdefghij", "abcdefghiX", True),
    ],
)
def test_numeric_and_text_support_preserves_targets(answer, line, keep):
    p = pool()
    b = batch(p, [answer])
    run = filter_batch(p, b, [ocr(p.samples[0], [line])], FilterConfig())
    d = run.decisions[0]
    assert d.f0_keep and d.f1_keep is keep
    assert d.answer_raw == answer and b.labels[0].answer_raw == answer
    assert d.semantic_check == "unknown"


def test_nfc_whitespace_does_not_rewrite_raw_or_case():
    p = pool()
    raw = unicodedata.normalize("NFD", "Cà\nphê")
    d = filter_batch(p, batch(p, [raw]), [ocr(p.samples[0], ["Cà phê"])], FilterConfig()).decisions[
        0
    ]
    assert d.f1_keep and d.answer_raw == raw and d.answer_normalized == "Cà phê"
    assert normalize(" CÀ phê ") != normalize("Cà phê")


def test_repeated_exact_occurrences_are_ambiguous():
    p = pool()
    d = filter_batch(
        p, batch(p, ["125"]), [ocr(p.samples[0], ["Subtotal 125", "Total 125"])], FilterConfig()
    ).decisions[0]
    assert not d.f1_keep and d.reason == "ambiguous_ocr_support"


def test_margin_considers_runner_up_outside_acceptance_threshold():
    choices = (
        Candidate("abcdefghiX", ("a",), 0, 1, True),
        Candidate("abcdefghXY", ("b",), 2, 3, True),
    )
    config = FilterConfig(text_max_normalized_edit_distance=0.10, min_candidate_margin=0.15)
    assert match_part("abcdefghij", choices, config).reason == "ambiguous_ocr_support"


def test_margin_exact_boundary_is_not_lost_to_float_rounding():
    target = "abcdefghijklmnopqrst"
    choices = (
        Candidate("abcdefghijklmnopqrXY", ("a",), 0, 1, True),
        Candidate("abcdefghijklmnopqXYZ", ("b",), 2, 3, True),
    )
    assert match_part(target, choices, FilterConfig()).support == "fuzzy"


def test_multipart_independent_support_and_raw_serialization():
    p = pool()
    raw = "Cà phê ¡sep¿ Trà xanh"
    d = filter_batch(
        p,
        batch(p, [raw], protocol="literal_separator_v1"),
        [ocr(p.samples[0], ["Cà phê", "unrelated", "Trà xanh"])],
        FilterConfig(),
    ).decisions[0]
    assert d.f1_keep and len(d.parts) == 2 and d.answer_raw == raw
    d = filter_batch(
        p,
        batch(p, ["Cà phê\nTrà xanh"]),
        [ocr(p.samples[0], ["Cà phê", "Trà xanh"])],
        FilterConfig(),
    ).decisions[0]
    assert d.f1_keep and len(d.parts) == 1  # newline is not inferred multipart


def test_multipart_cannot_reuse_evidence_and_invalid_parts_fail_f0():
    p = pool()
    for raw, reason, f0 in (
        ("ABC ¡sep¿ ABC", "overlapping_part_evidence", True),
        ("ABC ¡sep¿ ", "invalid_answer_parts", False),
    ):
        d = filter_batch(
            p,
            batch(p, [raw], protocol="literal_separator_v1"),
            [ocr(p.samples[0], ["ABC"])],
            FilterConfig(),
        ).decisions[0]
        assert d.reason == reason and d.f0_keep is f0 and not d.f1_keep
        assert d.answer_raw == raw


def test_failures_and_missing_stay_in_requested_counts():
    p = pool(3)
    b = batch(p, ["125", None, "not returned"])
    b = b.model_copy(update={"labels": b.labels[:2]})
    run = filter_batch(p, b, [], FilterConfig())
    assert [d.reason for d in run.decisions] == ["ocr_missing", "unanswerable", "missing_label"]
    assert summarize(run) == {
        "requested": 3,
        "f0_eligible": 1,
        "f1_kept": 0,
        "f1_retention": 0,
        "reasons": {"missing_label": 1, "ocr_missing": 1, "unanswerable": 1},
        "quality_measured": False,
        "semantic_correctness_verified": False,
    }
    all_failed = batch(p, [None, None, None])
    assert summarize(filter_batch(p, all_failed, [], FilterConfig()))["f1_retention"] is None


@pytest.mark.parametrize("field", ["gold", "answer", "references", "labels"])
def test_pool_rejects_hidden_gold(field):
    with pytest.raises(ValidationError):
        SilverPool.model_validate(pool().model_dump() | {field: "hidden"})


@pytest.mark.parametrize("partition", ["test", "ood", "dev_calibrate", "quarantine"])
def test_pool_does_not_enable_forbidden_partitions(partition):
    with pytest.raises(ValidationError):
        SilverPool.model_validate(pool().model_dump() | {"partition": partition})


def test_pool_gold_overlap_and_document_inconsistency_rejected():
    p = pool()
    with pytest.raises(ValidationError):
        SilverPool.model_validate(p.model_dump() | {"gold_samples": p.samples})
    second = sample(2, image_id=1).model_copy(update={"image_sha256": "c" * 64})
    with pytest.raises(ValidationError):
        SilverPool.model_validate(p.model_dump() | {"samples": (*p.samples, second)})


def test_duplicate_unknown_and_tampered_identities():
    p = pool()
    b = batch(p, ["125"])
    with pytest.raises(ValidationError):
        SilverBatch.model_validate(b.model_dump() | {"labels": (*b.labels, *b.labels)})
    for changed in (
        b.model_copy(update={"pool_sha256": "c" * 64}),
        b.model_copy(update={"labels": (b.labels[0].model_copy(update={"qid": "unknown"}),)}),
    ):
        with pytest.raises(ValueError):
            filter_batch(p, changed, [], FilterConfig())
    result = ocr(p.samples[0], ["125"])
    for results in ([result, result], [result.model_copy(update={"image_sha256": "c" * 64})]):
        with pytest.raises(ValueError):
            filter_batch(p, b, results, FilterConfig())


def test_api_result_and_floating_model_revision_rejected():
    p = pool()
    b = batch(p, ["125"])
    for change in ({"provider": "openai"}, {"model_revision": "main"}, {"usage": {}}):
        with pytest.raises(ValidationError):
            SilverBatch.model_validate(b.model_dump() | change)


def test_ocr_limits_and_duplicate_span_identity():
    p = pool()
    b = batch(p, ["ABC"])
    result = ocr(p.samples[0], ["ABC DEF"])
    d = filter_batch(p, b, [result], FilterConfig(max_document_tokens=1)).decisions[0]
    assert d.f0_keep and not d.f1_keep and d.reason == "ocr_token_limit"
    result.spans.append(result.spans[0])
    with pytest.raises(ValueError, match="span IDs"):
        filter_batch(p, b, [result], FilterConfig())


def test_holdout_requires_freeze_before_filter_or_gold():
    p = pool(partition="audit_holdout")
    with pytest.raises(PermissionError):
        filter_batch(p, batch(p, ["125"]), [], FilterConfig())
    with pytest.raises(ValidationError):
        FilterConfig(status="frozen_dev_select")


def test_filter_audit_denominators_slices_and_quality_bins():
    p = pool(4, "audit_holdout")
    b = batch(p, ["125", "999", "ABC", None])
    o = [
        ocr(s, [text])
        for s, text in zip(p.samples, ["125", "999", "different", "anything"], strict=True)
    ]
    run = filter_batch(p, b, o, frozen())
    refs = [
        GoldReference(qid=s.question.qid, document_id=s.question.document_id, answers=(a,))
        for s, a in zip(p.samples, ["125", "120", "ABC", "other"], strict=True)
    ]
    bins = {s.question.document_id: "readable" for s in p.samples}
    report = audit_filter(p, b, run, refs, quality_bins=bins)
    rates = report["overall"]
    assert rates["requested"] == 4 and rates["eligible"] == 3 and rates["kept"] == 2
    assert rates["label_accuracy"] == rates["retention"] == 2 / 3
    assert rates["filter_precision"] == rates["filter_recall"] == 0.5
    assert rates["false_accept"] == rates["false_reject"] == 1
    assert report["ocr_quality_bins"]["readable"] == rates
    assert report["by_answer_type"]["unknown"]["filter_precision"] is None
    with pytest.raises(ValueError):
        audit_filter(p, b, run, refs[:-1])
    with pytest.raises(ValueError):
        audit_filter(p, b, run, refs, quality_bins={})


def test_train_gold_never_a_filter_audit_input():
    p = pool()
    b = batch(p, ["125"])
    with pytest.raises(PermissionError):
        audit_filter(p, b, filter_batch(p, b, [], FilterConfig()), [])


def test_nine_experiments_share_budget_and_match_strata_without_gold_targets():
    p = pool(6)
    b = batch(p, ["125"] * 6)
    o = [ocr(s, ["125" if i % 2 else "999"]) for i, s in enumerate(p.samples)]
    run = filter_batch(p, b, o, frozen())
    approval = approve(p, b)
    plans = select_experiments(p, b, run, approval, HASH, 120)
    assert len(plans) == 9
    assert plans == select_experiments(p, b, run, approval, HASH, 120)
    by_arm = {arm: [x for x in plans if x.arm == arm] for arm in ("P1-full", "P1-size", "P2")}
    assert all(len(x.silver_qids) == 6 for x in by_arm["P1-full"])
    assert all(len(x.silver_qids) == 3 for x in by_arm["P1-size"] + by_arm["P2"])
    assert len({x.gold_qids for x in plans}) == 1
    assert all(
        x.optimizer_updates == 120 and x.fixture_only and not x.training_executed for x in plans
    )
    assert "answer" not in plans[0].model_dump()
    shuffled = run.model_copy(update={"decisions": tuple(reversed(run.decisions))})
    reordered = select_experiments(p, b, shuffled, approval, HASH, 120)
    assert [x.silver_qids for x in plans] == [x.silver_qids for x in reordered]


@pytest.mark.parametrize(
    "field",
    [
        "training_labels_allowed",
        "data_rights_verified",
        "model_license_verified",
        "quality_pilot_passed",
    ],
)
def test_training_selection_denied_without_each_gate(field):
    p = pool()
    b = batch(p, ["125"])
    run = filter_batch(p, b, [ocr(p.samples[0], ["125"])], frozen())
    with pytest.raises(PermissionError):
        select_experiments(p, b, run, approve(p, b).model_copy(update={field: False}), HASH, 10)


def test_selections_reject_wrong_scope_empty_f1_and_changed_answer():
    p = pool()
    b = batch(p, ["125"])
    run = filter_batch(p, b, [], frozen())
    with pytest.raises(ValueError, match="no labels"):
        select_experiments(p, b, run, approve(p, b), HASH, 10)
    altered = run.model_copy(
        update={"decisions": (run.decisions[0].model_copy(update={"answer_raw": "999"}),)}
    )
    with pytest.raises(ValueError):
        select_experiments(p, b, altered, approve(p, b), HASH, 10)


def test_bundle_roundtrip_replay_and_no_overwrite(tmp_path):
    p = pool()
    b = batch(p, ["125"])
    directory = tmp_path / "run"
    run = write_bundle(directory, p, b, [ocr(p.samples[0], ["125"])], FilterConfig())
    assert load_bundle(directory) == (p, b, run)
    before = {f.name: f.read_bytes() for f in directory.iterdir()}
    with pytest.raises(FileExistsError):
        write_bundle(directory, p, b, [], FilterConfig())
    assert before == {f.name: f.read_bytes() for f in directory.iterdir()}
    (directory / "run.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_bundle(directory)


def test_missing_bundle_marker_and_manifest_path_escape(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bundle(tmp_path)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {"protocol": "silver_filter_bundle_v1", "complete": True, "files": {"../escape": HASH}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="manifest"):
        load_bundle(tmp_path)


def test_bundle_rehash_cannot_hide_changed_decisions(tmp_path):
    from vidoclens.common.pilot import sha256

    p = pool()
    b = batch(p, ["125"])
    directory = tmp_path / "run"
    write_bundle(directory, p, b, [], FilterConfig())
    path = directory / "run.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["decisions"][0]["reason"] = "silently changed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["run.json"] = sha256(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="replay"):
        load_bundle(directory)


def test_matched_size_preserves_multiple_strata():
    from collections import Counter

    p = pool(4)
    samples = (
        *p.samples[:2],
        sample(3, question="Tên cửa hàng?"),
        sample(4, question="Tên cửa hàng?"),
    )
    p = p.model_copy(update={"samples": samples})
    b = batch(p, ["125", "900", "Cà phê", "Trà xanh"])
    results = [
        ocr(s, [text]) for s, text in zip(samples, ["125", "wrong", "Cà phê", "wrong"], strict=True)
    ]
    run = filter_batch(p, b, results, frozen())
    plans = select_experiments(p, b, run, approve(p, b), HASH, 10)
    strata = {d.qid: (d.question_type, d.answer_type) for d in run.decisions}
    target = Counter(strata[d.qid] for d in run.decisions if d.f1_keep)
    assert len(target) == 2
    for plan in plans:
        if plan.arm == "P1-size":
            assert Counter(strata[q] for q in plan.silver_qids) == target


@pytest.mark.parametrize("partition", ["dev_select", "audit_holdout"])
def test_heldout_labels_cannot_become_training_selections(partition):
    p = pool(partition=partition)
    b = batch(p, ["125"])
    run = filter_batch(p, b, [ocr(p.samples[0], ["125"])], frozen())
    with pytest.raises(PermissionError, match="train_fit"):
        select_experiments(p, b, run, approve(p, b), HASH, 10)


def test_approval_does_not_extend_to_another_batch():
    p = pool()
    b = batch(p, ["125"])
    run = filter_batch(p, b, [ocr(p.samples[0], ["125"])], frozen())
    wrong = approve(p, b).model_copy(update={"batch_sha256": "c" * 64})
    with pytest.raises(PermissionError):
        select_experiments(p, b, run, wrong, HASH, 10)


def test_synthetic_or_foreign_freeze_cannot_approve_real_run():
    p = pool()
    b = batch(p, ["125"])
    for changed_batch, config in (
        (b.model_copy(update={"fixture_only": False}), frozen()),
        (b, frozen().model_copy(update={"freeze_access_plan_sha256": "c" * 64})),
    ):
        with pytest.raises(ValueError, match="freeze belongs"):
            filter_batch(p, changed_batch, [], config)
