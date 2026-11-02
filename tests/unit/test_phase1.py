import json

import pytest
from pydantic import ValidationError
from test_image_ingestion import record

from vidoclens.contracts.dataset import ReceiptAccessPlan, ReceiptAssignment
from vidoclens.contracts.models import Box, OCRResult, OCRSpan
from vidoclens.contracts.review import OODAnnotation, TranscriptionReview
from vidoclens.data.freeze import access_plan, containment_groups, load_frozen_plan
from vidoclens.data.split_draft import draft_split
from vidoclens.eval.bootstrap import group_bootstrap
from vidoclens.eval.compatible import compatible_scores
from vidoclens.eval.oracle import answer_parts, character_error_rate, matched_ocr, spans
from vidoclens.ocr.cache import cache_key, load_cache, store_cache
from vidoclens.ocr.quality import select_pilot


def ocr(lines=("A", "125.000")):
    return OCRResult(
        document_id="doc",
        engine="test-fixture",
        engine_revision="1",
        preprocessing_hash="b" * 64,
        image_sha256="a" * 64,
        status="ok" if lines else "empty",
        spans=[
            OCRSpan(
                span_id=f"line-{i}",
                line_id=f"line-{i}",
                reading_order=i,
                text_raw=s,
                text_nfc=s,
                box=Box(x0=0, y0=0, x1=1, y1=1),
            )
            for i, s in enumerate(lines)
        ],
    )


def identity():
    return dict(
        document_id="doc",
        raw_image_sha256="a" * 64,
        canonical_pixel_sha256="b" * 64,
        preprocessing={"version": 1},
        language="vi",
        engine="fixture",
        detector="rev1",
        recognizer="rev2",
        package_lock_sha256="c" * 64,
    )


def test_uncertain_edges_contained_transitively_and_quarantined():
    rows = [record(1), record(2), record(3, "test"), record(4, "dev"), record(5)]
    groups = containment_groups(rows, {(1, 2), (2, 3), (3, 4)}, {1})
    draft = draft_split(rows, groups, "a" * 64)
    plan = access_plan(draft, 100, "b" * 64)
    roles = {a.source_image_id: a.partition for a in plan.assignments}
    assert roles == {1: "quarantine", 2: "quarantine", 3: "test", 4: "quarantine", 5: "train_fit"}
    assert all(not a.gold_for_training for a in plan.assignments if a.source_image_id != 5)
    assert len(groups) == 2
    assert all(g.grouping_evidence == "conservative_candidate_component" for g in groups)


@pytest.mark.parametrize("edges", [{(1, 99)}, {(2, 1)}, {(1, 1)}])
def test_bad_candidates_rejected(edges):
    with pytest.raises(ValueError):
        containment_groups([record(1), record(2)], edges, set())


def test_draft_nested_budgets_and_pilot_exclusion_with_containment():
    rows = [record(i) for i in range(1, 81)]
    groups = containment_groups(rows, {(1, 2), (2, 3)}, {1})
    a = draft_split(rows, groups, "a" * 64)
    b = draft_split(list(reversed(rows)), tuple(reversed(groups)), "a" * 64)
    assert a == b
    assert all(x.partition != "audit_holdout" for x in a.assignments if x.pilot_exposed)
    selected = [
        {x.source_image_id for x in access_plan(a, k, "b" * 64).assignments if x.gold_for_training}
        for k in (5, 10, 25, 100)
    ]
    assert selected[0] < selected[1] < selected[2] < selected[3]


def test_pilot_requires_frozen_gold_and_distinct_components():
    rows = [record(i) for i in range(1, 101)]
    groups = containment_groups(rows, {(1, 2)}, set())
    plan = access_plan(draft_split(rows, groups, "a" * 64), 100, "b" * 64)
    chosen = select_pilot(rows, plan, count=5)
    by_id = {a.source_image_id: a for a in plan.assignments}
    assert len({by_id[r.source_image_id].duplicate_group_id for r in chosen}) == 5
    assert all(by_id[r.source_image_id].gold_for_training for r in chosen)
    with pytest.raises(ValueError):
        select_pilot(rows, plan, count=100)


def test_conservative_plan_requires_evidence_and_quarantine_never_gold():
    with pytest.raises(ValidationError):
        ReceiptAssignment(
            source_image_id=1,
            source_split="train",
            duplicate_group_id="g",
            partition="quarantine",
            gold_for_training=True,
        )
    with pytest.raises(ValidationError):
        ReceiptAccessPlan(
            archive_sha256="a" * 64,
            grouping_status="conservative_candidate_graph",
            assignments=[
                ReceiptAssignment(
                    source_image_id=1,
                    source_split="train",
                    duplicate_group_id="g",
                    partition="train_fit",
                )
            ],
        )


def test_incomplete_freeze_rejected(tmp_path):
    (tmp_path / "summary.json").write_text(
        json.dumps({"status": "frozen_conservative", "uncontained_edges": 0, "files": {}})
    )
    with pytest.raises(ValueError):
        load_frozen_plan(tmp_path)


def test_cache_roundtrip_and_corruption_rejection(tmp_path):
    result = ocr()
    assert load_cache(tmp_path, identity()) is None
    key = store_cache(tmp_path, identity(), result)
    assert load_cache(tmp_path, identity()) == result
    assert store_cache(tmp_path, identity(), result) == key
    entry = json.loads((tmp_path / (key + ".json")).read_text())
    entry["result"]["spans"][0]["text_raw"] = "tampered"
    (tmp_path / (key + ".json")).write_text(json.dumps(entry))
    with pytest.raises(ValueError):
        load_cache(tmp_path, identity())


@pytest.mark.parametrize("field", list(identity()))
def test_cache_key_binds_every_configuration_field(field):
    base = identity()
    changed = {**base, field: "different"}
    assert cache_key(base) != cache_key(changed)


def test_cache_refuses_image_mismatch_and_conflicting_outputs(tmp_path):
    store_cache(tmp_path, identity(), ocr())
    with pytest.raises(ValueError):
        store_cache(tmp_path, identity(), ocr(("B",)))
    with pytest.raises(ValueError):
        store_cache(tmp_path, {**identity(), "document_id": "other"}, ocr())
    missing = identity()
    del missing["language"]
    with pytest.raises(ValueError):
        cache_key(missing)


def test_bootstrap_is_qa_weighted_and_clustered_not_qa_resampling():
    scores = {"a": 1.0, "b": 1.0, "c": 0.0}
    groups = {"a": "g1", "b": "g1", "c": "g2"}
    result = group_bootstrap(scores, groups, resamples=1000)
    assert result["point_estimate"] == pytest.approx(2 / 3)
    assert (result["lower_95"], result["upper_95"]) == (0, 1)
    assert result == group_bootstrap(dict(reversed(list(scores.items()))), groups, resamples=1000)
    delta = group_bootstrap(scores, groups, paired_scores=scores)
    assert delta["point_estimate"] == delta["lower_95"] == delta["upper_95"] == 0


@pytest.mark.parametrize(
    "scores,groups",
    [
        ({"a": 1}, {"b": "g"}),
        ({"a": float("nan")}, {"a": "g"}),
        ({"a": 2}, {"a": "g"}),
        ({"a": 1}, {"a": "g"}),
    ],
)
def test_bootstrap_rejects_bad_populations(scores, groups):
    with pytest.raises(ValueError):
        group_bootstrap(scores, groups)


def test_multipart_is_full_string_and_digit_not_fuzzy_fixed():
    choices = spans(ocr())
    assert matched_ocr(choices, ("A\n125.000",))["scores"]["strict_nfc_em"] == 1
    assert matched_ocr(choices, ("A\n125.001",))["scores"]["strict_nfc_em"] == 0
    assert matched_ocr(choices, ("A\nMISSING",))["scores"]["strict_nfc_em"] == 0
    assert answer_parts("A\r\nB ¡sep¿ C") == ("A", "B ", " C")
    assert matched_ocr((), ("abc",))["prediction"] is None


def test_span_cap_excludes_disconnected_and_long_answers():
    choices = spans(ocr(("a", "b", "c", "d", "e")))
    assert "a\nb\nc\nd" in choices
    assert "a\nb\nc\nd\ne" not in choices
    assert "a e" not in choices


def test_compatible_preserves_upstream_quirks_and_raw_separator():
    assert compatible_scores("a a", ["a a"])["set_token_f1"] == 0.5
    assert compatible_scores(" a ", ["a", "b"])["accuracy"] == 0.5
    assert compatible_scores("ĐỒNG", ["đồng"])["accuracy"] == 0
    assert compatible_scores("ĐỒNG", ["đồng"])["anls"] == 1
    assert compatible_scores("A ¡sep¿ B", ["A\nB"])["accuracy"] == 0
    assert compatible_scores("ab", ["ac"])["anls"] == 0
    assert compatible_scores(None, ["a"]) == dict(accuracy=0, set_token_f1=0, anls=0)


def test_cer_keeps_digits_and_reports_micro_denominator():
    result = character_error_rate([("125.001", "125.000"), ("é", "e\u0301")])
    assert result["edit_errors"] == 1
    assert result["reference_characters"] == 8
    assert result["cer"] == 0.125
    with pytest.raises(ValueError):
        character_error_rate([("x", "")])


def test_ai_review_cannot_be_promoted_to_human_gold():
    payload = dict(
        document_id="d",
        image_sha256="a" * 64,
        ocr_sha256="b" * 64,
        reviewer="assistant",
        reviewer_type="ai",
        reference_origin="image_transcription",
        blind_to_ocr_during_transcription=True,
        human_verified=False,
        coverage="selected_lines",
        lines=[dict(line_id="line-0", reference="125.000", legibility="readable")],
    )
    assert not TranscriptionReview(**payload).human_verified
    with pytest.raises(ValidationError):
        TranscriptionReview(**{**payload, "human_verified": True})
    with pytest.raises(ValidationError):
        OODAnnotation(
            document_id="d",
            image_sha256="a" * 64,
            rights_evidence_id="local-only",
            source_domain="fixture",
            shift_axes=["device"],
            question="Readable?",
            question_type="text",
            answerable=False,
            annotator="assistant",
            annotator_type="ai",
            second_review="ai_only",
            eligible_as_human_gold=True,
        )


def test_feature_rotation_candidate_synthetic():
    np = pytest.importorskip("numpy")
    from PIL import Image

    from vidoclens.data.feature_candidates import candidate_pairs, gradient_hash
    from vidoclens.data.images import phash64

    rng = np.random.default_rng(42)
    img = Image.fromarray(rng.integers(0, 255, size=(80, 50, 3), dtype=np.uint8))
    rows = []
    for i, im in enumerate((img, img.rotate(90, expand=True))):
        views = [im.rotate(a, expand=True) for a in (0, 90, 180, 270)]
        rows.append(
            dict(
                source_image_id=i,
                phash_rotations=[phash64(v) for v in views],
                crop60_phash=phash64(im),
                gradient_rotations=[gradient_hash(v) for v in views],
            )
        )
    assert len(list(candidate_pairs(rows))) == 1


def test_cache_atomic_publish_under_concurrent_writers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def publish(i):
        try:
            store_cache(tmp_path, identity(), ocr(("A" if i % 2 else "B",)))
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(publish, range(16)))
    assert any(outcomes) and not all(outcomes)
    assert load_cache(tmp_path, identity()).spans[0].text_raw in {"A", "B"}
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_long_ocr_line_cannot_bypass_registered_token_cap():
    long_line = " ".join(f"t{i}" for i in range(25))
    choices = spans(ocr((long_line,)))
    assert long_line not in choices
    assert all(len(s.split()) <= 24 for s in choices)


def test_bootstrap_refuses_unpaired_qids():
    with pytest.raises(ValueError):
        group_bootstrap({"a": 1, "b": 0}, {"a": "g1", "b": "g2"}, paired_scores={"a": 1})


def test_unknown_test_partition_never_exposes_evaluation_gold():
    from pathlib import Path

    from vidoclens.eval.receiptvqa_gold import load_evaluation_gold

    rows = [record(1), record(2, "test")]
    plan = access_plan(
        draft_split(rows, containment_groups(rows, set(), set()), "a" * 64), 100, "b" * 64
    )
    with pytest.raises(PermissionError):
        load_evaluation_gold(Path("does-not-exist.zip"), plan, partition="test")


def test_transcription_missing_detection_and_ai_provenance(tmp_path):
    from vidoclens.common.pilot import sha256, write_json
    from vidoclens.eval.transcription import evaluate_reviews

    (tmp_path / "images").mkdir()
    (tmp_path / "images/1.jpg").write_bytes(b"hash-fixture-not-real-image")
    result = ocr(("125.001",)).model_copy(update={"document_id": "fixture:image:1"})
    write_json(tmp_path / "ocr_1.json", result.model_dump())
    review = TranscriptionReview(
        document_id="fixture:image:1",
        image_sha256=sha256(tmp_path / "images/1.jpg"),
        ocr_sha256=sha256(tmp_path / "ocr_1.json"),
        reviewer="fixture",
        reviewer_type="ai",
        reference_origin="image_transcription",
        human_verified=False,
        blind_to_ocr_during_transcription=True,
        coverage="selected_lines",
        lines=[
            dict(line_id="line-0", reference="125.000", legibility="readable"),
            dict(line_id="missing-1", reference="abc", legibility="readable"),
            dict(line_id="missing-2", reference="unclear", legibility="uncertain"),
        ],
    )
    write_json(tmp_path / "review.json", review.model_dump())
    report = evaluate_reviews([tmp_path / "review.json"], tmp_path)
    assert report["by_reviewer_type"]["ai"]["edit_errors"] == 4
    assert report["by_reviewer_type"]["ai"]["reference_characters"] == 10
    assert report["uncertain_lines_excluded"] == 1
    assert report["missing_detections_included_as_deletions"] == 1
    assert not report["human_review_available"]
    (tmp_path / "images/1.jpg").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        evaluate_reviews([tmp_path / "review.json"], tmp_path)
