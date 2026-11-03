"""Synthetic spatial evidence; never a model quality or calibration benchmark."""

import json
import unicodedata

import pytest
from pydantic import ValidationError
from test_silver import HASH, sample

from vidoclens.common.pilot import sha256
from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.models import Box, OCRResult, OCRSpan
from vidoclens.contracts.verification import (
    PipelineBinding,
    PredictionObservation,
    VerificationBatch,
    VerificationPool,
    VerifierConfig,
    VerifierInput,
    VerifierProfile,
)
from vidoclens.eval.verification import evaluate_verifier
from vidoclens.filtering.io import digest
from vidoclens.verify.bundle import load_bundle, write_bundle
from vidoclens.verify.verifier import implementation_hash, verify


def profile(*, frozen=False, config=None, access=HASH):
    return VerifierProfile(
        config=config or VerifierConfig(),
        binding=PipelineBinding(
            student_bundle_sha256=HASH,
            student_protocol_sha256=HASH,
            filter_config_sha256=HASH,
            fallback_profile_sha256=HASH,
            g4_evidence_sha256=HASH,
            fixture_only=True,
        ),
        access_plan_sha256=access,
        implementation_sha256=implementation_hash(),
        status="frozen_dev_select" if frozen else "candidate",
        selection_evidence_sha256=HASH if frozen else None,
    )


def ocr(s, lines):
    """Distinct whole-line boxes in reading order, with one field per line."""
    return OCRResult(
        document_id=s.question.document_id,
        image_sha256=s.image_sha256,
        engine="synthetic",
        engine_revision="1",
        preprocessing_hash=HASH,
        status="ok" if lines else "empty",
        spans=[
            OCRSpan(
                span_id=f"s{i}",
                line_id=f"l{i}",
                reading_order=i,
                text_raw=text,
                text_nfc=unicodedata.normalize("NFC", text),
                box=Box(x0=0.05, x1=0.95, y0=0.05 + i * 0.15, y1=0.10 + i * 0.15),
            )
            for i, text in enumerate(lines)
        ],
    )


def value(answer="125", lines=("Tổng tiền 125",), question="Tổng tiền?", *, index=1):
    s = sample(index, source="dev", question=question)
    return VerifierInput(
        sample=s,
        prediction=AnswerPrediction(
            qid=s.question.qid,
            status="answered" if answer is not None else "abstained",
            answer_raw=answer,
        ),
        ocr=ocr(s, lines),
    )


def pool(values, *, partition="dev_select"):
    return VerificationPool(
        partition=partition,
        archive_sha256=HASH,
        access_plan_sha256=HASH,
        inventory_sha256=HASH,
        samples=tuple(v.sample for v in values),
    )


def batch(p, values, prof, *, teacher=False, cost=10):
    return VerificationBatch(
        pool_sha256=digest(p),
        binding=prof.binding,
        source="fallback_teacher" if teacher else "student",
        cache_regime="synthetic",
        observations=tuple(
            PredictionObservation(
                prediction=v.prediction,
                cost_micro_usd=cost if teacher else 0,
                latency_ms=100 if teacher else 10,
                external_requests=1 if teacher else 0,
                image_transmissions=1 if teacher else 0,
            )
            for v in values
        ),
    )


@pytest.mark.parametrize(
    "answer,line,accepted",
    [
        ("125", "Tổng tiền 125", True),
        ("125", "Tổng tiền 126", False),
        ("12", "Tổng tiền 125.000", False),
        ("007", "Tổng tiền 7", False),
        ("007", "Tổng tiền 007", True),
        ("12", "Tổng tiền - 12", False),
        ("-12", "Tổng tiền 12", False),
        ("12", "Tổng tiền ( 12 )", False),
        ("12", "Tổng tiền 12 €", False),
        ("12", "Tổng tiền 12 kg", False),
        ("1,5", "Tổng tiền 15", False),
        ("1,5", "Tổng tiền 1,5", True),
        ("125.000 đ", "Tổng tiền 125.000 đ", True),
        ("125.000", "Tổng tiền 125.000 đ", False),
        ("12", "Tổng tiền 12 / 05 / 2026", False),
    ],
)
def test_numeric_exact_and_no_digit_sign_unit_edit(answer, line, accepted):
    v = value(answer, [line])
    for snap in (False, True):
        result = verify(v, VerifierConfig(), snap=snap)
        assert (result.status == "answered") == accepted
        assert result.answer_before == answer and not result.snap_applied
        assert result.answer_after == (answer if accepted else None)
        assert result.calibrated_confidence is None


def test_text_snap_preserves_raw_with_occurrence_and_recheck():
    v = value("Nguyễn Trãi", ["Địa chỉ Nguyễn Trái"], "Địa chỉ?")
    checked = verify(v, VerifierConfig())
    snapped = verify(v, VerifierConfig(), snap=True)
    assert checked.answer_after == checked.answer_before == "Nguyễn Trãi"
    assert snapped.snap_applied and snapped.answer_after == "Nguyễn Trái"
    assert snapped.answer_before == "Nguyễn Trãi"
    assert snapped.parts[0].selected.field_status == "pass"
    assert snapped.parts[0].selected.span_ids == ("s0",)
    assert snapped.parts[0].selected.boxes and snapped.parts[0].alternatives
    assert 0 < snapped.rule_score < 1


@pytest.mark.parametrize(
    "v,reason",
    [
        (value("200", ["Tổng tiền 125", "Khách đưa 200"]), "wrong_field_risk"),
        (value("125", ["125"]), "field_unknown"),
        (value("125", ["Tổng tiền 125"], "Số hóa đơn?"), "field_unknown"),
        (value("125", ["Tổng tiền 125", "Tổng tiền 125"]), "ambiguous_span"),
        (value(None), "prediction_abstained"),
        (value("125", []), "ocr_unavailable"),
    ],
)
def test_fail_closed(v, reason):
    result = verify(v, VerifierConfig(), snap=True)
    assert result.status == "abstained" and result.reason == reason
    assert result.answer_after is None


def test_margin_counts_runner_up_beyond_threshold():
    # First candidate distance .05; second .10, with a required .06 margin.
    v = value(
        "abcdefghijklmnopqrst",
        ["Địa chỉ abcdefghijklmnopqrsX", "Địa chỉ abcdefghijklmnopqrXY"],
        "Địa chỉ?",
    )
    cfg = VerifierConfig(text_threshold=0.05, candidate_margin=0.06)
    assert verify(v, cfg, snap=True).reason == "ambiguous_span"


def test_short_text_and_hybrid_not_fuzzy_edited():
    assert (
        verify(value("Hà", ["Địa chỉ Há"], "Địa chỉ?"), VerifierConfig(), snap=True).status
        == "abstained"
    )
    v = value("12 Nguyễn Trãi", ["Địa chỉ 12 Nguyễn Trái"], "Địa chỉ?")
    assert verify(v, VerifierConfig(), snap=True).status == "abstained"


def test_separated_label_geometry_and_wrong_nearest_field():
    v = value("125", ["Tổng tiền", "125"])
    label, amount = v.ocr.spans
    label.box = Box(x0=0.05, y0=0.1, x1=0.4, y1=0.15)
    amount.box = Box(x0=0.6, y0=0.1, x1=0.9, y1=0.15)
    assert verify(v, VerifierConfig()).status == "answered"
    label.text_raw = label.text_nfc = "Khách đưa"
    assert verify(v, VerifierConfig()).reason == "wrong_field_risk"
    label.box = Box(x0=0.05, y0=0.8, x1=0.4, y1=0.9)
    assert verify(v, VerifierConfig()).reason == "field_unknown"


def test_multi_part_literal_needs_distinct_evidence_and_limits():
    cfg = VerifierConfig(part_protocol="literal_separator_v1")
    v = value(
        "Nguyễn Trãi¡sep¿Thanh Xuân", ["Địa chỉ Nguyễn Trãi", "Địa chỉ Thanh Xuân"], "Địa chỉ?"
    )
    assert verify(v, cfg, snap=True).answer_after == v.prediction.answer_raw
    repeated = v.model_copy(
        update={
            "prediction": v.prediction.model_copy(
                update={"answer_raw": "Nguyễn Trãi¡sep¿Nguyễn Trãi"}
            )
        }
    )
    assert verify(repeated, cfg).reason == "overlapping_part_evidence"
    empty = v.model_copy(
        update={"prediction": v.prediction.model_copy(update={"answer_raw": "Nguyễn Trãi¡sep¿"})}
    )
    assert verify(empty, cfg).reason == "empty literal answer part"
    assert verify(v, VerifierConfig(max_document_tokens=1)).reason == "ocr_token_limit"
    assert verify(v, VerifierConfig(max_answer_characters=1)).reason == "answer_length_limit"


def test_mutable_ocr_revalidation_and_identity():
    v = value()
    v.ocr.spans[0].text_nfc = "different"
    with pytest.raises(ValueError, match="NFC"):
        verify(v, VerifierConfig())
    with pytest.raises(ValidationError, match="qid mismatch"):
        VerifierInput(sample=v.sample, prediction=AnswerPrediction(qid="other", status="error"))
    clean = value()
    clean.ocr.image_sha256 = "b" * 64
    with pytest.raises(ValueError, match="image mismatch"):
        verify(clean, VerifierConfig())


def test_bundle_replay_hashes_and_raw_denominator(tmp_path):
    values = [
        value(),
        value("Nguyễn Trãi", ["Địa chỉ Nguyễn Trái"], "Địa chỉ?", index=2),
        value(index=3),
    ]
    p, prof = pool(values), profile()
    b = batch(p, values[:2], prof)
    output = tmp_path / "verification"
    write_bundle(output, p, b, [v.ocr for v in values], prof)
    assert load_bundle(output)[-1]["P3-check"][2].reason == "prediction_error"
    refs = [
        GoldReference(
            qid=v.prediction.qid,
            document_id=v.sample.question.document_id,
            answers=("Nguyễn Trái" if i == 1 else "125",),
        )
        for i, v in enumerate(values)
    ]
    report = evaluate_verifier(p, b, [v.ocr for v in values], prof, refs, resamples=20)
    assert report["metrics"]["P2"]["n_missing"] == 1
    assert report["metrics"]["P3-snap"]["strict_nfc_em"] == 2 / 3
    assert report["snap"]["corrected"] == 1 and report["snap"]["numeric_edits"] == 0
    assert report["snap"]["correction_precision"] == 1
    with pytest.raises(FileExistsError):
        write_bundle(output, p, b, [v.ocr for v in values], prof)
    data = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
    data["P3-snap"][0]["answer_after"] = "FORGED"
    (output / "decisions.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_bundle(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["decisions.json"] = sha256(output / "decisions.json")
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="replay differs"):
        load_bundle(output)


def test_harm_is_counted_and_abstention_is_separate():
    values = [
        value("Nguyễn Trãi", ["Địa chỉ Nguyễn Trái"], "Địa chỉ?"),
        value("125", ["125"], index=2),
    ]
    p, prof = pool(values), profile()
    refs = [
        GoldReference(
            qid=v.prediction.qid,
            document_id=v.sample.question.document_id,
            answers=(v.prediction.answer_raw,),
        )
        for v in values
    ]
    result = evaluate_verifier(
        p, batch(p, values, prof), [v.ocr for v in values], prof, refs, resamples=20
    )
    assert result["snap"]["harmed"] == 1 and result["snap"]["harm_among_correct_edited"] == 1
    assert result["correct_predictions_abstained"]["P3-snap"] == 1


def test_profile_code_change_and_calibration_freeze_are_enforced():
    v, prof = value(), profile()
    with pytest.raises(PermissionError, match="freeze"):
        evaluate_verifier(
            pool([v], partition="dev_calibrate"),
            batch(pool([v], partition="dev_calibrate"), [v], prof),
            [v.ocr],
            prof,
            [],
        )
    wrong = prof.model_copy(update={"implementation_sha256": HASH})
    with pytest.raises(ValueError, match="implementation changed"):
        evaluate_verifier(pool([v]), batch(pool([v]), [v], wrong), [v.ocr], wrong, [])
