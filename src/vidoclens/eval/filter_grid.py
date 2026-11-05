"""Enumerate dev-only F1 thresholds; record an explicit, reviewable selection."""

import json

from vidoclens.common.pilot import sha256
from vidoclens.contracts.silver import FilterConfig
from vidoclens.eval.silver import audit_filter
from vidoclens.filtering.bundle import load_bundle, write_bundle
from vidoclens.filtering.io import digest, revalidate, write_model

THRESHOLDS = {"tau-000": 0.0, "tau-005": 0.05, "tau-010": 0.10, "tau-015": 0.15}


def run_grid(pool, batch, ocr, base, references, output, *, quality_bins=None):
    pool, base = revalidate(pool), revalidate(base)
    if pool.partition != "dev_select" or base.status != "pilot_defaults_not_calibrated":
        raise PermissionError("threshold search is limited to unfrozen dev_select rules")
    references, ocr = list(references), list(ocr)
    output.mkdir(parents=True, exist_ok=False)
    rows = {}
    for name, threshold in THRESHOLDS.items():
        config = FilterConfig.model_validate(
            base.model_dump() | {"text_max_normalized_edit_distance": threshold}
        )
        run = write_bundle(output / name, pool, batch, ocr, config)
        report = audit_filter(pool, batch, run, references, quality_bins=quality_bins)
        write_model(output / name / "audit.json", report)
        rows[name] = {
            "threshold": threshold,
            "config_sha256": digest(config),
            "bundle_manifest_sha256": sha256(output / name / "manifest.json"),
            "audit_sha256": sha256(output / name / "audit.json"),
            "overall": report["overall"],
        }
    report = {
        "protocol": "f1_dev_grid_v1",
        "complete": True,
        "partition": "dev_select",
        "pool_sha256": digest(pool),
        "batch_sha256": digest(batch),
        "access_plan_sha256": pool.access_plan_sha256,
        "fixture_only": batch.fixture_only,
        "candidates": rows,
        "selected": None,
        "selection_policy": (
            "owner reviews precision/recall/retention and records rationale; no automatic optimum"
        ),
    }
    write_model(output / "grid.json", report)
    return report


def load_grid(directory):
    grid = json.loads((directory / "grid.json").read_text(encoding="utf-8"))
    if (
        grid.get("protocol") != "f1_dev_grid_v1"
        or grid.get("complete") is not True
        or set(grid.get("candidates", {})) != set(THRESHOLDS)
    ):
        raise ValueError("invalid/incomplete dev grid")
    baseline, reports, configs = None, {}, {}
    for name, threshold in THRESHOLDS.items():
        row = grid["candidates"][name]
        if (
            sha256(directory / name / "manifest.json") != row["bundle_manifest_sha256"]
            or sha256(directory / name / "audit.json") != row["audit_sha256"]
        ):
            raise ValueError("dev grid evidence checksum mismatch")
        pool, batch, run = load_bundle(directory / name)
        report = json.loads((directory / name / "audit.json").read_text(encoding="utf-8"))
        common_config = run.config.model_dump(exclude={"text_max_normalized_edit_distance"})
        signature = (
            digest(pool),
            digest(batch),
            run.ocr_sha256,
            common_config,
            report.get("reference_sha256"),
            report.get("quality_bins_sha256"),
        )
        if baseline is not None and signature != baseline:
            raise ValueError("grid candidates must share inputs and all non-threshold settings")
        baseline = signature
        if (
            pool.partition != "dev_select"
            or run.config.status != "pilot_defaults_not_calibrated"
            or run.config.text_max_normalized_edit_distance != threshold
            or row["threshold"] != threshold
            or row["config_sha256"] != digest(run.config)
            or grid["pool_sha256"] != digest(pool)
            or grid["batch_sha256"] != digest(batch)
            or grid["partition"] != "dev_select"
            or grid["fixture_only"] is not batch.fixture_only
            or grid["access_plan_sha256"] != pool.access_plan_sha256
            or report.get("protocol") != "strict_nfc_em_filter_audit_v1"
            or report.get("partition") != "dev_select"
            or report.get("filter_run_sha256") != digest(run)
            or report.get("config_sha256") != digest(run.config)
            or report.get("overall") != row["overall"]
            or report.get("pool_sha256") != digest(pool)
            or report.get("fixture_only") is not batch.fixture_only
            or report.get("access_plan_sha256") != pool.access_plan_sha256
        ):
            raise ValueError("grid/report provenance mismatch")
        reports[name], configs[name] = report, run.config
    return grid, reports, configs


def select_grid(directory, candidate, output, *, selected_by, rationale):
    grid, _, configs = load_grid(directory)
    if candidate not in configs or not selected_by.strip() or not rationale.strip():
        raise ValueError("selection needs a known candidate, reviewer and tradeoff rationale")
    selection = {
        "protocol": "f1_dev_grid_selection_v1",
        "partition": "dev_select",
        "grid_sha256": sha256(directory / "grid.json"),
        "candidate": candidate,
        "all_candidates": grid["candidates"],
        "selected_by": selected_by,
        "rationale": rationale,
        "access_plan_sha256": grid["access_plan_sha256"],
        "fixture_only": grid["fixture_only"],
    }
    output.mkdir(parents=True, exist_ok=False)
    write_model(output / "selection.json", selection)
    config = FilterConfig.model_validate(
        configs[candidate].model_dump()
        | {
            "status": "frozen_dev_select",
            "freeze_evidence_sha256": sha256(output / "selection.json"),
            "freeze_access_plan_sha256": grid["access_plan_sha256"],
            "freeze_fixture_only": grid["fixture_only"],
        }
    )
    write_model(output / "config.json", config)
    write_model(
        output / "manifest.json",
        {
            "complete": True,
            "files": {n: sha256(output / n) for n in ("selection.json", "config.json")},
        },
    )
    return config
