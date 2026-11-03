"""Synthetic grid, blinded review and honest clustered/seed comparison checks."""

import json

import pytest
from test_silver import HASH, approve, batch, frozen, ocr, pool, sample

from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.silver import FilterConfig
from vidoclens.contracts.silver_results import SilverTrainingResult
from vidoclens.contracts.silver_review import SilverHumanReview
from vidoclens.eval.filter_grid import load_grid, run_grid, select_grid
from vidoclens.eval.silver_comparison import compare_results
from vidoclens.eval.silver_review import make_review_packet, summarize_review
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest, write_model
from vidoclens.filtering.pipeline import filter_batch


def gold_for(p, answers):
    return [
        GoldReference(qid=s.question.qid, document_id=s.question.document_id, answers=(answer,))
        for s, answer in zip(p.samples, answers, strict=True)
    ]


def test_grid_completeness_and_selection_provenance(tmp_path):
    p = pool(2, "dev_select")
    b = batch(p, ["abcdefghij", "123"])
    evidence = [ocr(p.samples[0], ["abcdefghiX"]), ocr(p.samples[1], ["123"])]
    root = tmp_path / "grid"
    report = run_grid(p, b, evidence, FilterConfig(), gold_for(p, ["abcdefghij", "123"]), root)
    assert len(report["candidates"]) == 4 and report["selected"] is None
    assert report["candidates"]["tau-000"]["overall"]["kept"] == 1
    assert report["candidates"]["tau-010"]["overall"]["kept"] == 2
    chosen = select_grid(
        root,
        "tau-010",
        tmp_path / "freeze",
        selected_by="fixture",
        rationale="synthetic tradeoff only",
    )
    assert chosen.freeze_fixture_only is True and chosen.freeze_access_plan_sha256 == HASH
    with pytest.raises(FileExistsError):
        select_grid(root, "tau-010", tmp_path / "freeze", selected_by="fixture", rationale="repeat")
    (root / "tau-005" / "audit.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        load_grid(root)


@pytest.mark.parametrize("partition", ["train_fit", "audit_holdout"])
def test_grid_denies_non_dev_before_evaluating(partition, tmp_path):
    p = pool(partition=partition)
    with pytest.raises(PermissionError):
        run_grid(p, batch(p, ["1"]), [], FilterConfig(), [], tmp_path / "grid")
    assert not (tmp_path / "grid").exists()


def test_blind_sampling_and_complete_human_import():
    p = pool(4, "dev_select")
    b = batch(p, ["1", "2", "3", "4"])
    evidence = [ocr(s, [value]) for s, value in zip(p.samples, ["1", "2", "0", "0"], strict=True)]
    run = filter_batch(p, b, evidence, FilterConfig())
    packet, key, template = make_review_packet(
        p, b, run, gold_for(p, ["1", "0", "3", "0"]), evidence, per_stratum=1
    )
    assert len(packet.items) == 4 and all(r["sampled"] == 1 for r in key["strata"].values())
    serialized = packet.model_dump_json()
    assert all(
        word not in serialized
        for word in ("kept_correct", "reference", "gold_reference", "f1_keep")
    )
    assert template["image_inspection_attested"] is False
    with pytest.raises(ValueError):
        SilverHumanReview.model_validate(template)
    template.update(reviewer="synthetic fixture", image_inspection_attested=True)
    for row in template["judgments"]:
        row.update(correctness="correct", semantic_field="correct", ocr_quality="good")
    review = SilverHumanReview.model_validate(template)
    summary = summarize_review(packet, key, review)
    assert (
        summary["reviewed"] == 4
        and summary["fixture_only"] is True
        and summary["gold_modified"] is False
    )
    assert summary["by_stratum"]["kept_wrong"]["disagreements_with_automatic_gold_em"] == 1
    for changed in (
        review.model_copy(update={"judgments": review.judgments[:-1]}),
        review.model_copy(update={"fixture_only": False}),
    ):
        with pytest.raises(ValueError):
            summarize_review(packet, key, changed)


def test_review_sampling_deterministic_with_empty_strata():
    p = pool(8, "dev_select")
    b = batch(p, ["1"] * 8)
    evidence = [ocr(s, ["1"]) for s in p.samples]
    run = filter_batch(p, b, evidence, FilterConfig())
    args = (p, b, run, gold_for(p, ["1"] * 8), evidence)
    packet, key, _ = make_review_packet(*args, per_stratum=3, seed=17)
    assert packet == make_review_packet(*args, per_stratum=3, seed=17)[0]
    assert packet != make_review_packet(*args, per_stratum=3, seed=42)[0]
    assert key["strata"]["kept_correct"]["inclusion_probability"] == 3 / 8
    assert key["strata"]["kept_wrong"]["inclusion_probability"] is None


@pytest.fixture
def comparison():
    train = pool(3)
    b = batch(train, ["1", "2", "3"])
    run = filter_batch(train, b, [ocr(s, ["1"]) for s in train.samples], frozen())
    plans = select_experiments(train, b, run, approve(train, b), HASH, 100)
    dev = pool(3, "dev_select").model_copy(
        update={"samples": tuple(sample(i, source="dev") for i in (201, 202, 203))}
    )
    refs = gold_for(dev, ["1", "2", "3"])
    results = []
    for seed in (17, 42, 2026):
        for arm in ("L2", "P1-full", "P1-size", "P2"):
            plan = next((p for p in plans if p.arm == arm and p.seed == seed), None)
            silver = plan.silver_qids if plan else ()
            # Deliberately log zero exposure for selected but unseen candidates.
            counts = {q: 3 if i == 0 else 0 for i, q in enumerate(silver)}
            results.append(
                SilverTrainingResult(
                    arm=arm,
                    seed=seed,
                    run_id=f"fixture-{arm}-{seed}",
                    fixture_only=True,
                    training_pool_sha256=digest(train),
                    evaluation_pool_sha256=digest(dev),
                    selection_sha256=digest(plan) if plan else None,
                    training_profile_sha256=HASH,
                    evaluation_profile_sha256=HASH,
                    g3_evidence_sha256=HASH,
                    checkpoint_sha256=HASH,
                    optimizer_updates_completed=100,
                    gold_qids=(train.gold_samples[0].question.qid,),
                    silver_qids=silver,
                    gold_exposure_counts={train.gold_samples[0].question.qid: 3},
                    silver_exposure_counts=counts,
                    training_seconds=1.0,
                    peak_reserved_bytes=1,
                    predictions=tuple(
                        AnswerPrediction(
                            qid=s.question.qid,
                            status="answered",
                            answer_raw=str(i + 1) if arm == "P2" else "wrong",
                        )
                        for i, s in enumerate(dev.samples)
                    ),
                )
            )
    return train, dev, refs, plans, results


def test_comparison_12_runs_paired_seed_statistics(comparison):
    report = compare_results(*comparison, resamples=30)
    assert len(report["runs"]) == 12 and report["fixture_only"] is True
    assert report["seed_summary"]["P2"]["strict_nfc_em"]["mean"] == 1
    assert report["seed_summary"]["P2"]["strict_nfc_em"]["sample_std"] == 0
    ci = report["paired_em"]["P2_vs_P1-size"]
    assert ci["primary"] is True and ci["training_seed_delta_mean"] == 1
    assert ci["fixed_three_seed_mean_group_bootstrap"]["lower_95"] == 1
    assert ci["fixed_three_seed_mean_group_bootstrap"]["training_variance_included"] is False
    assert report["runs"]["P1-full/17"]["selected_silver"] == 3
    assert report["runs"]["P1-full/17"]["seen_unique_silver"] == 1
    assert report["g4_automatically_passed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("training_profile_sha256", "b" * 64),
        ("optimizer_updates_completed", 99),
        ("evaluation_profile_sha256", "b" * 64),
        ("g3_evidence_sha256", "b" * 64),
        ("fixture_only", False),
        ("evaluation_pool_sha256", "b" * 64),
        ("training_pool_sha256", "b" * 64),
    ],
)
def test_unfair_comparisons_fail(comparison, field, value):
    train, dev, refs, plans, results = comparison
    results[0] = results[0].model_copy(update={field: value})
    with pytest.raises(ValueError):
        compare_results(train, dev, refs, plans, results, resamples=2)


def test_missing_predictions_stay_in_denominator(comparison):
    train, dev, refs, plans, results = comparison
    i = next(i for i, r in enumerate(results) if r.arm == "P2")
    results[i] = results[i].model_copy(update={"predictions": results[i].predictions[:1]})
    report = compare_results(train, dev, refs, plans, results, resamples=2)
    metrics = report["runs"]["P2/17"]["metrics"]
    assert metrics["n_missing"] == 2 and metrics["strict_nfc_em"] == 1 / 3


def test_duplicate_runs_unknown_predictions_and_group_leakage_rejected(comparison):
    train, dev, refs, plans, results = comparison
    for altered in (results[:-1], results + results[:1], [results[0]] * 12):
        with pytest.raises(ValueError):
            compare_results(train, dev, refs, plans, altered)
    leaked = dev.model_copy(
        update={
            "samples": (
                dev.samples[0].model_copy(
                    update={"duplicate_group_id": train.samples[0].duplicate_group_id}
                ),
                *dev.samples[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="groups overlap"):
        compare_results(train, leaked, refs, plans, results)
    unknown = results[0].predictions[0].model_copy(update={"qid": "unknown"})
    results[0] = results[0].model_copy(update={"predictions": (unknown,)})
    with pytest.raises(ValueError, match="unknown"):
        compare_results(train, dev, refs, plans, results)


def test_atomic_writes_do_not_replace_or_publish_partial_json(tmp_path):
    path = tmp_path / "artifact.json"
    write_model(path, {"ok": True})
    with pytest.raises(FileExistsError):
        write_model(path, {"ok": False})
    assert json.loads(path.read_text())["ok"] is True
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(TypeError):
        write_model(tmp_path / "invalid.json", {"bad": object()})
    assert not (tmp_path / "invalid.json").exists()
