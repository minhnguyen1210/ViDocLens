"""Synthetic archive to frozen verifier/router and OOD preregistration, without final gold."""

import json
import zipfile

import pytest
from pydantic import ValidationError
from test_ood_review import plan as ood_plan
from test_ood_review import submissions
from test_silver import HASH
from test_silver_workflow import arguments
from test_silver_workflow import source as source
from test_verifier import batch, ocr, pool, profile, value

from vidoclens.common.pilot import sha256
from vidoclens.contracts.calibration import RoutingGridPlan
from vidoclens.contracts.dataset import GoldReference
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.final_suite import FinalSuitePlan
from vidoclens.contracts.verification import VerificationPool, VerifierInput, VerifierProfile
from vidoclens.eval.routing import routing_grid
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.verify.__main__ import main
from vidoclens.verify.pool import make_pool


def test_routing_pareto_usage_unknowns_and_error_denominator():
    # At .9 accept fuzzy student locally; at 1 require verified fallback.
    values = [value(), value("Nguyễn Trãi", ["Địa chỉ Nguyễn Trái"], "Địa chỉ?", index=2)]
    p, prof = pool(values, partition="dev_calibrate"), profile(frozen=True)
    teacher_values = [
        values[0],
        values[1].model_copy(
            update={
                "prediction": values[1].prediction.model_copy(update={"answer_raw": "Nguyễn Trái"})
            }
        ),
    ]
    student, teacher = batch(p, values, prof), batch(p, teacher_values, prof, teacher=True)
    refs = [
        GoldReference(
            qid=v.prediction.qid,
            document_id=v.sample.question.document_id,
            answers=(v.prediction.answer_raw,),
        )
        for v in teacher_values
    ]
    plan = RoutingGridPlan(
        pool_sha256=digest(p),
        verifier_profile_sha256=digest(prof),
        fixture_only=True,
        thresholds=(0.9, 1.0),
        external_eligible_qids=tuple(r.qid for r in refs),
    )
    report = routing_grid(
        p, student, teacher, [v.ocr for v in values], prof, plan, refs, resamples=20
    )
    a, b = report["points"]
    assert a["local_coverage"] == 1 and a["cost_micro_usd"] == 0 and a["targets_met"]
    assert b["fallback_selections"] == b["external_requests"] == 1
    assert b["cost_ratio_vs_teacher_all"] == 0.5 and b["pareto_dominated"]
    assert b["metrics"]["strict_nfc_em"] == 1 and b["recorded_stage_sum_p95_ms"] > 10
    for cost in (None, 0):
        unknown = batch(p, teacher_values, prof, teacher=True, cost=cost)
        got = routing_grid(
            p, student, unknown, [v.ocr for v in values], prof, plan, refs, resamples=20
        )
        assert got["points"][1]["cost_ratio_vs_teacher_all"] is None
        assert not got["points"][1]["targets_met"]
    missing = student.model_copy(update={"observations": student.observations[:1]})
    unknown_usage = teacher.model_copy(
        update={
            "observations": tuple(
                o.model_copy(update={"external_requests": None, "image_transmissions": None})
                for o in teacher.observations
            )
        }
    )
    unknown_report = routing_grid(
        p, student, unknown_usage, [v.ocr for v in values], prof, plan, refs, resamples=20
    )
    assert unknown_report["points"][1]["external_requests"] is None
    assert unknown_report["points"][1]["image_transmissions"] is None
    got = routing_grid(p, missing, teacher, [v.ocr for v in values], prof, plan, refs, resamples=20)
    assert got["points"][0]["metrics"]["strict_nfc_em"] == 0.5
    assert got["points"][0]["fallback_selections"] == 0
    assert got["points"][0]["recorded_stage_sum_p50_ms"] is None
    with pytest.raises(ValueError, match="all qids"):
        routing_grid(
            p,
            student,
            teacher.model_copy(update={"observations": teacher.observations[:1]}),
            [v.ocr for v in values],
            prof,
            plan,
            refs,
        )
    with pytest.raises(ValidationError, match="cache/fixture"):
        routing_grid(
            p,
            student,
            teacher.model_copy(update={"cache_regime": "cache_hit"}),
            [v.ocr for v in values],
            prof,
            plan,
            refs,
        )


def test_no_test_ood_train_access_and_pre_freeze_calibration(source):
    for partition in ("train_fit", "audit_holdout", "test", "ood", "dev_calibrate"):
        with pytest.raises(PermissionError):
            make_pool(*source, partition)
    dev = make_pool(*source, "dev_select")
    assert len(dev.samples) == 1 and "GOLD_MUST" not in dev.model_dump_json()


def test_full_cli_freeze_replay_preregister_without_final_gold(source, tmp_path, monkeypatch):
    original = zipfile.ZipFile.read

    def guarded(self, name, *args, **kwargs):
        assert "test.csv" not in name
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", guarded)
    common = arguments(source)
    prof_path = tmp_path / "candidate.json"
    dev = make_pool(*source, "dev_select")
    prof = profile(access=dev.access_plan_sha256)
    pp, binding_path = tmp_path / "profile-pool.json", tmp_path / "binding.json"
    write_model(pp, dev)
    write_model(binding_path, prof.binding)
    main(["profile", "--pool", str(pp), "--binding", str(binding_path), "--output", str(prof_path)])
    assert read_model(prof_path, VerifierProfile) == prof

    def make_bundle(partition, current_profile, current_profile_path):
        pp = tmp_path / f"{partition}.json"
        main(
            [
                "prepare",
                *common,
                "--partition",
                partition,
                "--profile",
                str(current_profile_path),
                "--output",
                str(pp),
            ]
        )
        p = read_model(pp, VerificationPool)
        values = [
            VerifierInput(
                sample=s,
                prediction=AnswerPrediction(
                    qid=s.question.qid, status="answered", answer_raw="125"
                ),
                ocr=ocr(s, ["Total 125"]),
            )
            for s in p.samples
        ]
        bp, op = tmp_path / f"{partition}-predictions.json", tmp_path / f"{partition}-ocr.jsonl"
        b = batch(p, values, current_profile)
        write_model(bp, b)
        op.write_text("\n".join(v.ocr.model_dump_json() for v in values) + "\n", encoding="utf-8")
        output = tmp_path / f"{partition}-bundle"
        main(
            [
                "verify",
                "--pool",
                str(pp),
                "--student",
                str(bp),
                "--ocr",
                str(op),
                "--profile",
                str(current_profile_path),
                "--output",
                str(output),
            ]
        )
        return p, values, output

    _, _, bundle = make_bundle("dev_select", prof, prof_path)
    audit = tmp_path / "audit.json"
    main(["audit", *common, "--bundle", str(bundle), "--output", str(audit)])
    report = json.loads(audit.read_text(encoding="utf-8"))
    assert report["metrics"]["P3-check"]["strict_nfc_em"] == 1
    frozen = tmp_path / "verifier-freeze"
    selection = ["--selected-by", "synthetic-reviewer", "--rationale", "synthetic workflow only"]
    main(["freeze-verifier", *common, "--bundle", str(bundle), *selection, "--output", str(frozen)])
    prof_path = frozen / "profile.json"
    prof = read_model(prof_path, VerifierProfile)
    assert prof.selection_evidence_sha256 == sha256(frozen / "selection.json")
    cal, values, bundle = make_bundle("dev_calibrate", prof, prof_path)
    teacher_path, plan_path = tmp_path / "teacher.json", tmp_path / "grid-plan.json"
    write_model(teacher_path, batch(cal, values, prof, teacher=True))
    write_model(
        plan_path,
        RoutingGridPlan(
            pool_sha256=digest(cal),
            verifier_profile_sha256=digest(prof),
            fixture_only=True,
            external_eligible_qids=tuple(v.prediction.qid for v in values),
        ),
    )
    grid = tmp_path / "grid"
    main(
        [
            "routing-grid",
            *common,
            "--bundle",
            str(bundle),
            "--teacher",
            str(teacher_path),
            "--plan",
            str(plan_path),
            "--output",
            str(grid),
        ]
    )
    route = tmp_path / "routing-freeze"
    main(
        [
            "routing-select",
            *common,
            "--grid",
            str(grid),
            "--threshold",
            "1",
            *selection,
            "--output",
            str(route),
        ]
    )

    op = tmp_path / "ood-plan.json"
    plan = ood_plan(source[2])
    write_model(op, plan)
    packets = tmp_path / "packets"
    main(
        ["ood-packets", "--plan", str(op), "--inventory", str(source[2]), "--output", str(packets)]
    )
    primary, second = submissions(plan, source[2])
    ap, bp = tmp_path / "human-a.json", tmp_path / "human-b.json"
    write_model(ap, primary)
    write_model(bp, second)
    curated = tmp_path / "curated"
    main(
        [
            "ood-curate",
            "--plan",
            str(op),
            "--inventory",
            str(source[2]),
            "--primary",
            str(ap),
            "--second",
            str(bp),
            "--output",
            str(curated),
        ]
    )
    systems = tmp_path / "systems.json"
    write_model(
        systems,
        {
            f"{arm}/{seed}": HASH
            for arm in ("L2", "P1-full", "P1-size", "P2")
            for seed in (17, 42, 2026)
        }
        | {"teacher-all": HASH},
    )
    final = tmp_path / "final-plan.json"
    final_args = [
        "preregister",
        "--routing-freeze",
        str(route),
        "--ood-curation",
        str(curated),
        "--systems",
        str(systems),
        "--frozen",
        str(source[1]),
        "--inventory",
        str(source[2]),
        "--output",
        str(final),
    ]
    main(final_args)
    manifest = read_model(final, FinalSuitePlan)
    assert manifest.test_image_ids == (7,) and manifest.fixture_only
    assert not manifest.execution_enabled and not manifest.g5_certified
    for change in (
        {"execution_enabled": True},
        {"additional_comparisons": ()},
        {"systems": {"teacher-all": HASH}},
        {"frozen_access_plan_sha256": "b" * 64},
    ):
        with pytest.raises(ValidationError):
            FinalSuitePlan.model_validate(manifest.model_dump() | change)
    with pytest.raises(FileExistsError):
        main(final_args)
    report = json.loads((grid / "report.json").read_text(encoding="utf-8"))
    report["points"][0]["cost_micro_usd"] = 9999
    (grid / "report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        main(
            [
                "routing-select",
                *common,
                "--grid",
                str(grid),
                "--threshold",
                "1",
                *selection,
                "--output",
                str(tmp_path / "forged"),
            ]
        )
    manifest = json.loads((grid / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["report.json"] = sha256(grid / "report.json")
    (grid / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="replay differs"):
        main(
            [
                "routing-select",
                *common,
                "--grid",
                str(grid),
                "--threshold",
                "1",
                *selection,
                "--output",
                str(tmp_path / "forged-replay"),
            ]
        )
