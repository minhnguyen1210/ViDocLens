"""Small synthetic archive -> frozen pool -> filter/audit -> nine selection files."""

import csv
import io
import json
import zipfile

import pytest
from test_image_ingestion import record
from test_silver import HASH, approve, batch, ocr

from vidoclens.common.pilot import sha256
from vidoclens.contracts.dataset import ReceiptAccessPlan, ReceiptAssignment
from vidoclens.contracts.silver import FilterConfig, SilverPool
from vidoclens.data.audit_receiptvqa import COLUMNS, PREFIX
from vidoclens.filtering.__main__ import main
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.filtering.pool import make_pool


@pytest.fixture
def source(tmp_path):
    archive = tmp_path / "annotations.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for split, ids in (("train", [1, 2, 3, 4]), ("dev", [5, 6]), ("test", [7])):
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            for row, index in enumerate(ids):
                writer.writerow(
                    [
                        row,
                        index,
                        0,
                        f"{index}.png",
                        "Total?",
                        "125" if index == 5 else "GOLD_MUST_NOT_ENTER_FILTER",
                    ]
                )
            z.writestr(f"{PREFIX}ReceiptVQA_{split}.csv", stream.getvalue())
    ah = sha256(archive)
    assignments, images, groups = [], [], []
    for index, partition in enumerate(
        (
            "train_fit",
            "train_fit",
            "train_fit",
            "audit_holdout",
            "dev_select",
            "dev_calibrate",
            "test",
        ),
        1,
    ):
        split = "train" if index < 5 else "dev" if index < 7 else "test"
        assignments.append(
            ReceiptAssignment(
                source_image_id=index,
                source_split=split,
                partition=partition,
                duplicate_group_id=f"g{index}",
                gold_for_training=index == 1,
            )
        )
        images.append(
            record(index, split).model_copy(
                update={
                    "document_id": f"receiptvqa:{ah}:image:{index}",
                    "annotation_archive_sha256": ah,
                    "qa_count": 1,
                }
            )
        )
        groups.append({"duplicate_group_id": f"g{index}", "source_image_ids": [index]})
    inventory = tmp_path / "inventory.jsonl"
    inventory.write_text("\n".join(r.model_dump_json() for r in images) + "\n", encoding="utf-8")
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    write_model(frozen / "containment_groups.json", {"groups": groups})
    write_model(frozen / "partition_membership.json", {"fixture": True})
    plan = ReceiptAccessPlan(
        archive_sha256=ah,
        grouping_status="conservative_candidate_graph",
        image_inventory_sha256=sha256(inventory),
        candidate_graph_sha256=sha256(frozen / "containment_groups.json"),
        assignments=tuple(assignments),
    )
    for k in (5, 10, 25, 100):
        write_model(frozen / f"access_g{k}.json", plan)
    write_model(
        frozen / "summary.json",
        {
            "status": "frozen_conservative",
            "uncontained_edges": 0,
            "files": {p.name: sha256(p) for p in frozen.iterdir()},
        },
    )
    return archive, frozen, inventory


def arguments(source):
    return [
        v
        for key, path in zip(("archive", "frozen", "inventory"), source, strict=True)
        for v in ("--" + key, str(path))
    ]


def test_pool_exact_membership_no_gold_or_test_access(source, monkeypatch):
    original = zipfile.ZipFile.read

    def guarded(self, name, *args, **kwargs):
        assert "test.csv" not in name
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", guarded)
    for partition, ids in (("train_fit", [2, 3]), ("dev_select", [5]), ("audit_holdout", [4])):
        p = make_pool(*source, partition)
        assert [s.question.source_image_id for s in p.samples] == ids
        assert "GOLD_MUST" not in p.model_dump_json()
        if partition == "train_fit":
            assert [s.question.source_image_id for s in p.gold_samples] == [1]
    with pytest.raises(PermissionError):
        make_pool(*source, "test")


def test_pool_rejects_changed_inventory_before_output(source):
    source[2].write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="frozen plan"):
        make_pool(*source, "train_fit")


def test_cli_complete_offline_handoff(source, tmp_path):
    config = tmp_path / "config.json"
    write_model(config, FilterConfig())
    common = arguments(source)

    def prepare(partition):
        path = tmp_path / f"{partition}-pool.json"
        main(["prepare", *common, "--partition", partition, "--output", str(path)])
        p = read_model(path, SilverPool)
        b = batch(p, ["125"] * len(p.samples))
        bp, op = tmp_path / f"{partition}-batch.json", tmp_path / f"{partition}-ocr.jsonl"
        write_model(bp, b)
        op.write_text(
            "\n".join(ocr(s, ["Total 125"]).model_dump_json() for s in p.samples) + "\n",
            encoding="utf-8",
        )
        return p, b, ["--pool", str(path), "--batch", str(bp), "--ocr", str(op)]

    dev, dev_batch, dev_args = prepare("dev_select")
    dev_run = tmp_path / "dev-run"
    main(["filter", *dev_args, "--config", str(config), "--output", str(dev_run)])
    report = tmp_path / "dev-report.json"
    main(["audit", *common, "--bundle", str(dev_run), "--output", str(report)])
    metrics = json.loads(report.read_text(encoding="utf-8"))
    assert metrics["overall"]["filter_precision"] == 1
    assert metrics["fixture_only"] and metrics["pool_sha256"] == digest(dev)
    selected_config = tmp_path / "frozen-config.json"
    main(
        [
            "freeze",
            "--config",
            str(config),
            "--dev-report",
            str(report),
            "--output",
            str(selected_config),
        ]
    )
    train, train_batch, train_args = prepare("train_fit")
    train_run = tmp_path / "train-run"
    main(["filter", *train_args, "--config", str(selected_config), "--output", str(train_run)])
    approval = tmp_path / "approval.json"
    write_model(approval, approve(train, train_batch))
    profile = tmp_path / "training-profile.json"
    write_model(profile, {"synthetic_fixture": True, "not_a_real_training_profile": True})
    out = tmp_path / "selections"
    main(
        [
            "select",
            *common,
            "--bundle",
            str(train_run),
            "--approval",
            str(approval),
            "--training-profile",
            str(profile),
            "--optimizer-updates",
            "10",
            "--output",
            str(out),
        ]
    )
    plans = [json.loads(p.read_text(encoding="utf-8")) for p in out.glob("P*.json")]
    assert len(plans) == 9 and all(p["fixture_only"] and not p["training_executed"] for p in plans)
    assert {p["training_profile_sha256"] for p in plans} == {sha256(profile)}
    assert "GOLD_MUST" not in (out / "silver_targets.json").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        main(["filter", *train_args, "--config", str(selected_config), "--output", str(train_run)])
    with pytest.raises(PermissionError):
        main(
            [
                "audit",
                *common,
                "--bundle",
                str(train_run),
                "--output",
                str(tmp_path / "forbidden.json"),
            ]
        )
    assert not (tmp_path / "forbidden.json").exists()


def test_freeze_refuses_holdout_and_wrong_config(tmp_path):
    config = tmp_path / "config.json"
    write_model(config, FilterConfig())
    for index, change in enumerate(({"partition": "audit_holdout"}, {"config_sha256": HASH})):
        report = tmp_path / f"report-{index}.json"
        write_model(
            report,
            {
                "protocol": "strict_nfc_em_filter_audit_v1",
                "partition": "dev_select",
                "config_sha256": digest(FilterConfig()),
                **change,
            },
        )
        output = tmp_path / f"frozen-{index}.json"
        with pytest.raises(ValueError, match="dev_select"):
            main(
                [
                    "freeze",
                    "--config",
                    str(config),
                    "--dev-report",
                    str(report),
                    "--output",
                    str(output),
                ]
            )
        assert not output.exists()
