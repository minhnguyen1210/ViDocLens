"""CPU-only G3 boundary stubs around the real Phase 4 preparation and loader."""

import json

import pytest
from test_silver import HASH, approve, batch, ocr
from test_silver_workflow import source  # noqa: F401

from vidoclens.common.pilot import sha256
from vidoclens.contracts.dataset import ReceiptAccessPlan
from vidoclens.contracts.distillation import DistillationConfig, Phase4Criteria, Phase4GateReport
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.silver import FilterConfig
from vidoclens.contracts.student import StudentConfig, StudentQuestion, StudentTrainingExample
from vidoclens.distillation import data
from vidoclens.filtering.bundle import write_bundle
from vidoclens.filtering.io import write_model
from vidoclens.filtering.pool import make_pool


@pytest.fixture
def prepared(source, tmp_path, monkeypatch):  # noqa: F811
    archive, frozen, inventory = source
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    records = [CorpusImage.model_validate_json(s) for s in inventory.read_text().splitlines()]
    updated, mapping = [], {}
    for r in records:
        image = inputs / f"{r.source_image_id}.bin"
        image.write_bytes(f"synthetic image {r.source_image_id}".encode())
        updated.append(r.model_copy(update={"raw_image_sha256": sha256(image)}))
        mapping[r.document_id] = image.name
    inventory.write_text("".join(r.model_dump_json() + "\n" for r in updated), encoding="utf-8")
    for path in frozen.glob("access_*.json"):
        plan = ReceiptAccessPlan.model_validate_json(path.read_text())
        path.write_text(
            plan.model_copy(update={"image_inventory_sha256": sha256(inventory)}).model_dump_json()
        )
    summary = json.loads((frozen / "summary.json").read_text())
    summary["files"] = {name: sha256(frozen / name) for name in summary["files"]}
    (frozen / "summary.json").write_text(json.dumps(summary))
    training = make_pool(*source, "train_fit")
    dev_pool = make_pool(*source, "dev_select").model_copy(
        update={"evaluation_cohort_sha256": HASH}
    )
    write_model(inputs / "dev_select.json", dev_pool)
    write_model(inputs / "image_map.json", mapping)
    for relative in (
        "artifacts/phase3/g3_report_v1.json",
        "artifacts/phase3/data_v2/manifest.json",
        "artifacts/phase3/dev_protocol_v2.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"fixture_only":true}')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("fixture prompt")
    config = StudentConfig(
        protocol="phase3_gold_v2",
        attention_backend="math",
        deterministic_algorithms=True,
        prompt_path="prompt.txt",
    )
    recipe = DistillationConfig(
        student=config, evaluation_cohort_sha256=HASH, g3_evidence_sha256=HASH
    )

    def question(s, partition):
        return StudentQuestion(
            question=s.question,
            partition=partition,
            duplicate_group_id=s.duplicate_group_id,
            image_sha256=s.image_sha256,
            image_path="inputs/" + mapping[s.question.document_id],
        )

    gold = [
        StudentTrainingExample(input=question(s, "train_fit"), answer_raw="authorized gold")
        for s in training.gold_samples
    ]
    dev = [question(s, "dev_select") for s in dev_pool.samples]
    monkeypatch.setattr(
        data,
        "load_gold_plan",
        lambda *args: (config, gold, dev, {"split_sha256": HASH, "environment_lock_sha256": HASH}),
    )
    monkeypatch.setattr(data, "profile", lambda root: recipe)
    monkeypatch.setattr(data, "source_paths", lambda root: source)
    monkeypatch.setattr(data, "COHORT_SHA256", HASH)
    monkeypatch.setattr(data, "implementation_files", lambda root: {"prompt.txt": sha256(prompt)})
    # Explicit test-only provenance stub: no GPU model is loaded or claimed by this fixture.
    labels = batch(training, [" 001,50 đ\n", "999"]).model_copy(update={"fixture_only": False})
    config_filter = FilterConfig(
        status="frozen_dev_select",
        freeze_fixture_only=False,
        freeze_access_plan_sha256=training.access_plan_sha256,
        freeze_evidence_sha256=HASH,
    )
    bundle = tmp_path / "bundle"
    write_bundle(
        bundle, training, labels, [ocr(s, ["001,50 đ"]) for s in training.samples], config_filter
    )
    approval_path = tmp_path / "approval.json"
    write_model(approval_path, approve(training, labels))
    selections = data.prepare(tmp_path, bundle, approval_path, inputs, tmp_path / "plans")
    return tmp_path, selections, gold, dev


def test_prepare_and_load_all_nine_plans_preserve_raw_targets_and_g10(prepared):
    root, selections, gold, dev = prepared
    assert len(selections) == 9
    for selection in selections:
        _, rows, actual_dev, manifest = data.load_plan(
            root, root / "plans" / f"{selection.arm}-{selection.seed}"
        )
        assert actual_dev == dev and manifest["gold_qa"] == len(gold)
        silver = [r.answer_raw for r in rows if r.source == "silver"]
        if selection.arm == "P2":
            assert silver == [" 001,50 đ\n"]
        assert {r.input.question.qid for r in rows if r.source == "gold"} == set(
            selection.gold_qids
        )


@pytest.mark.parametrize("corruption", ["raw_target", "group", "gold", "source", "approval"])
def test_loader_rejects_tampered_payload_even_if_local_file_hash_recomputed(prepared, corruption):
    root, _, _, _ = prepared
    plan = root / "plans/P2-17"
    manifest_path = plan / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if corruption == "approval":
        path = root / "approval.json"
        obj = json.loads(path.read_text())
        obj["training_labels_allowed"] = False
        path.write_text(json.dumps(obj))
        manifest["dependencies"]["approval.json"] = sha256(path)
    elif corruption == "source":
        (root / "prompt.txt").write_text("changed code stand-in")
    else:
        path = plan / "train.jsonl"
        rows = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
        if corruption == "gold":
            rows[0]["answer_raw"] = "hidden silver gold injection"
        elif corruption == "raw_target":
            rows[-1]["answer_raw"] = "001,50 đ"
        else:
            rows[-1]["input"]["duplicate_group_id"] = "other-group"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        manifest["files"]["train.jsonl"] = sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, PermissionError)):
        data.load_plan(root, plan)


def test_g4_negative_h2_is_allowed_but_missing_human_cannot_pass():
    values = {name: True for name in Phase4Criteria.model_fields if name != "schema_version"}
    base = dict(
        criteria=Phase4Criteria(**values),
        evidence={"fixture": HASH},
        h2_primary_difference=-0.02,
        limitations=("synthetic contract test",),
    )
    assert Phase4GateReport(status="pass", **base).h2_positive_required is False
    values["human_error_review"] = False
    base["criteria"] = Phase4Criteria(**values)
    with pytest.raises(ValueError):
        Phase4GateReport(status="pass", **base)
    assert Phase4GateReport(status="incomplete", **base).status == "incomplete"


@pytest.mark.parametrize("corruption", ["trajectory", "checkpoint", "partial_preflight", "proof"])
def test_smoke_evidence_binds_actual_files_after_success(prepared, corruption):
    from vidoclens.distillation.sampler import exposure_counts, schedule_digest
    from vidoclens.distillation.smoke_evidence import verify
    from vidoclens.distillation.train import sample_schedule

    # Synthetic bytes only; this test never invokes GPU code or creates real run evidence.
    root, _, _, _ = prepared
    plans, campaign = root / "plans", root / "synthetic-campaign"
    plan = plans / "P1-full-17"
    config, rows, dev, manifest = data.load_plan(root, plan)
    order = sample_schedule(rows, config, 17, "smoke")
    order_hash, plan_hash = schedule_digest(rows, order), sha256(plan / "manifest.json")
    campaign.mkdir()
    preflight = {
        "status": "pass",
        "plan_sha256": plan_hash,
        "populations": {
            name: {"n": n, "truncated": 0, "max_sequence": 100}
            for name, n in (("train", len(rows)), ("dev", len(dev)))
        },
    }
    write_model(campaign / "preflight.json", preflight)
    proof = {
        "status": "pass",
        "fixture_only": True,
        "plan_sha256": plan_hash,
        "schedule_sha256": order_hash,
        "continuous_updates": 52,
        "resumed_updates": 2,
        "mixed_source_exposures_verified": True,
        "resume_greedy_tokens_equal": True,
        "fresh_process_reload_tokens_equal": True,
        "optimizer_scheduler_rng_restored": True,
    }
    for name, prefix, begin in (("smoke", "continuous", 0), ("smoke-resumed", "resumed", 50)):
        directory = campaign / name
        directory.mkdir()
        records = []
        for step in (25, 50, 52) if not begin else (52,):
            checkpoint = directory / f"checkpoint-{step:04d}"
            (checkpoint / "adapter").mkdir(parents=True)
            files = (
                "training_state.pt",
                "adapter/adapter_config.json",
                "adapter/adapter_model.safetensors",
            )
            for relative in files:
                (checkpoint / relative).write_bytes(b"synthetic fixture; not model weights")
            write_model(
                checkpoint / "checkpoint.json",
                {
                    "complete": True,
                    "accumulation_pending": 0,
                    "plan_sha256": plan_hash,
                    "step": step,
                    "schedule_sha256": order_hash,
                    "exposures": exposure_counts(rows, order[: step * 16]),
                    "files": {relative: sha256(checkpoint / relative) for relative in files},
                },
            )
            records.append(
                {
                    "path": checkpoint.relative_to(root).as_posix(),
                    "sha256": sha256(checkpoint / "checkpoint.json"),
                }
            )
        run = {
            "fixture_only": True,
            "complete": True,
            "kind": "smoke",
            "seed": 17,
            "start_step": begin,
            "last_step": 52,
            "plan_sha256": plan_hash,
            "source_hashes": manifest["source_hashes"],
            "exposures": exposure_counts(rows, order),
            "schedule_sha256": order_hash,
            "checkpoints": records,
            "steps": [
                {
                    "step": i,
                    "loss": 0.5,
                    "grad_norm": 0.1,
                    "seconds": 1.0,
                    "peak_reserved_bytes": 1024,
                }
                for i in range(begin + 1, 53)
            ],
        }
        write_model(directory / "run.json", run)
        proof[prefix + "_run_sha256"] = sha256(directory / "run.json")
        proof[prefix + "_tail_losses"] = [0.5, 0.5]
    write_model(campaign / "resume_proof.json", proof)
    assert verify(root, plans, campaign) == proof
    if corruption == "trajectory":
        path = campaign / "smoke/run.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["steps"][0]["loss"] = 0.25
        path.write_text(json.dumps(value), encoding="utf-8")
    elif corruption == "checkpoint":
        (campaign / "smoke/checkpoint-0050/training_state.pt").write_bytes(b"changed")
    elif corruption == "partial_preflight":
        preflight["populations"]["train"]["n"] -= 1
        (campaign / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
    else:
        proof["fresh_process_reload_tokens_equal"] = False
        (campaign / "resume_proof.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(ValueError):
        verify(root, plans, campaign)
