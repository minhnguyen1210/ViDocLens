"""Synthetic frozen archive -> grid -> review -> twelve-result comparison CLI."""

import json

import pytest
from test_silver import HASH, approve, batch, ocr
from test_silver_workflow import arguments
from test_silver_workflow import source as source

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import (
    LocalModelSnapshot,
    LocalTeacherConfig,
    LocalTeacherPlan,
)
from vidoclens.contracts.silver import FilterConfig, SilverPool
from vidoclens.contracts.silver_results import SilverTrainingResult
from vidoclens.filtering.__main__ import main
from vidoclens.filtering.bundle import load_bundle, write_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.pool import make_pool
from vidoclens.teacher.local_cli import main as local_main


def test_extended_cli_workflow(source, tmp_path):
    common = arguments(source)
    dev = make_pool(*source, "dev_select")
    train = make_pool(*source, "train_fit")
    for name, value in (
        ("dev_pool", dev),
        ("train_pool", train),
        ("dev_batch", batch(dev, ["125"])),
        ("config", FilterConfig()),
    ):
        write_model(tmp_path / f"{name}.json", value)
    path = tmp_path / "ocr.jsonl"
    path.write_text(ocr(dev.samples[0], ["125"]).model_dump_json() + "\n", encoding="utf-8")
    grid, freeze, review = (tmp_path / n for n in ("grid", "freeze", "review"))
    main(
        [
            "grid",
            *common,
            "--pool",
            str(tmp_path / "dev_pool.json"),
            "--batch",
            str(tmp_path / "dev_batch.json"),
            "--ocr",
            str(path),
            "--config",
            str(tmp_path / "config.json"),
            "--output",
            str(grid),
        ]
    )
    main(
        [
            "grid-select",
            "--grid",
            str(grid),
            "--candidate",
            "tau-000",
            "--selected-by",
            "synthetic-test",
            "--rationale",
            "fixture exact threshold only",
            "--output",
            str(freeze),
        ]
    )
    config = read_model(freeze / "config.json", FilterConfig)
    main(
        [
            "review-export",
            *common,
            "--bundle",
            str(grid / "tau-000"),
            "--per-stratum",
            "1",
            "--output",
            str(review),
        ]
    )
    form = json.loads((review / "review_template.json").read_text(encoding="utf-8"))
    form.update(reviewer="synthetic-test-only", image_inspection_attested=True)
    for judgment in form["judgments"]:
        judgment.update(correctness="correct", semantic_field="correct", ocr_quality="good")
    write_model(tmp_path / "human.json", form)
    main(
        [
            "review-import",
            "--packet-dir",
            str(review),
            "--review",
            str(tmp_path / "human.json"),
            "--output",
            str(tmp_path / "human_summary.json"),
        ]
    )
    assert json.loads((tmp_path / "human_summary.json").read_text())["fixture_only"] is True
    b = batch(train, ["1", "2"])
    bundle = tmp_path / "train_bundle"
    write_bundle(bundle, train, b, [ocr(s, ["1"]) for s in train.samples], config)
    train, b, run = load_bundle(bundle)
    permission = approve(train, b)
    write_model(tmp_path / "approval.json", permission)
    write_model(tmp_path / "profile.json", {"synthetic_fixture_only": True})
    profile_hash = sha256(tmp_path / "profile.json")
    plans = select_experiments(train, b, run, permission, profile_hash, 10)
    paths = []
    gold = tuple(s.question.qid for s in train.gold_samples)
    for seed in (17, 42, 2026):
        for arm in ("L2", "P1-full", "P1-size", "P2"):
            plan = next((p for p in plans if p.arm == arm and p.seed == seed), None)
            silver = plan.silver_qids if plan else ()
            result = SilverTrainingResult(
                arm=arm,
                seed=seed,
                run_id=f"fixture-{arm}-{seed}",
                fixture_only=True,
                training_pool_sha256=digest(train),
                evaluation_pool_sha256=digest(dev),
                selection_sha256=digest(plan) if plan else None,
                training_profile_sha256=profile_hash,
                evaluation_profile_sha256=HASH,
                g3_evidence_sha256=HASH,
                checkpoint_sha256=HASH,
                optimizer_updates_completed=10,
                gold_qids=gold,
                silver_qids=silver,
                gold_exposure_counts={q: 2 for q in gold},
                silver_exposure_counts={q: 2 if i == 0 else 0 for i, q in enumerate(silver)},
                training_seconds=1,
                peak_reserved_bytes=1,
                predictions=(),
            )
            path = tmp_path / f"{arm}-{seed}.json"
            write_model(path, result)
            paths.append(str(path))
    output = tmp_path / "comparison"
    main(
        [
            "compare",
            *common,
            "--train-bundle",
            str(bundle),
            "--approval",
            str(tmp_path / "approval.json"),
            "--training-profile",
            str(tmp_path / "profile.json"),
            "--optimizer-updates",
            "10",
            "--pool",
            str(tmp_path / "dev_pool.json"),
            "--results",
            *paths,
            "--resamples",
            "2",
            "--output",
            str(output),
        ]
    )
    result = json.loads((output / "comparison.json").read_text())
    assert len(result["runs"]) == 12
    assert result["runs"]["P2/17"]["metrics"]["n_missing"] == 1
    assert result["paired_em"]["P2_vs_P1-size"]["per_seed"]["17"]["lower_95"] is None
    assert (output / "seed_summary.csv").is_file() and (output / "manifest.json").is_file()


@pytest.mark.parametrize("command", ["grid", "compare"])
def test_cli_forbidden_pool_before_gold_access(source, tmp_path, monkeypatch, command):
    p = make_pool(*source, "train_fit")
    write_model(tmp_path / "pool.json", p)

    def forbidden(*args, **kwargs):
        pytest.fail("gold was opened")

    monkeypatch.setattr("vidoclens.filtering.offline_cli.load_evaluation_gold", forbidden)
    args = [
        command,
        *arguments(source),
        "--pool",
        str(tmp_path / "pool.json"),
        "--output",
        str(tmp_path / "out"),
    ]
    extra = (
        ["batch", "ocr", "config"]
        if command == "grid"
        else ["train-bundle", "approval", "training-profile", "results"]
    )
    for name in extra:
        args += ["--" + name, str(tmp_path / "nonexistent")]
    if command == "compare":
        args += ["--optimizer-updates", "10"]
    with pytest.raises(PermissionError):
        main(args)
    assert not (tmp_path / "out").exists()


def test_local_plan_cli_never_imports_ml(source, tmp_path, monkeypatch):
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers", "bitsandbytes"}:
            pytest.fail("planning imported ML")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    p = make_pool(*source, "train_fit")
    write_model(tmp_path / "pool.json", p)
    snapshot_path = tmp_path / "snapshot.json"
    write_model(
        snapshot_path,
        LocalModelSnapshot(
            model_id="synthetic/local", model_revision="b" * 40, files={"config.json": HASH}
        ),
    )
    local_main(
        ["config", "--snapshot", str(snapshot_path), "--output", str(tmp_path / "config.json")]
    )
    cfg = read_model(tmp_path / "config.json", LocalTeacherConfig)
    assert cfg.snapshot_manifest_sha256 == sha256(snapshot_path)
    local_main(
        [
            "plan",
            *arguments(source),
            "--pool",
            str(tmp_path / "pool.json"),
            "--config",
            str(tmp_path / "config.json"),
            "--output",
            str(tmp_path / "plan.json"),
        ]
    )
    plan = read_model(tmp_path / "plan.json", LocalTeacherPlan)
    assert plan.pool_sha256 == digest(read_model(tmp_path / "pool.json", SilverPool))
    assert "GOLD_MUST_NOT_ENTER_FILTER" not in (tmp_path / "plan.json").read_text()
