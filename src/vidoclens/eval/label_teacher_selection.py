"""Select between the two preregistered local label formats on the identical dev cohort."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.distillation.inputs import COHORT_SHA256, G3_EVIDENCE_SHA256
from vidoclens.filtering.io import write_model

CRITERIA = {
    "complete_cohort",
    "answered_at_least_90_percent",
    "no_inference_errors",
    "strict_em_at_least_frozen_L1",
    "actual_gpu_measurements",
}


def choose(reports):
    if {r["generation_mode"] for r in reports} != {"raw_single_v1", "structured_batch_v1"} or len(
        reports
    ) != 2:
        raise ValueError("selection requires both preregistered candidates")
    if len({(r["pool_sha256"], r["cohort_sha256"], r["g3_sha256"]) for r in reports}) != 1:
        raise ValueError("candidate evaluation population differs")
    if any(
        r["cohort_sha256"] != COHORT_SHA256
        or r["g3_sha256"] != G3_EVIDENCE_SHA256
        or r["strict"]["n_questions"] != 666
        or set(r["criteria"]) != CRITERIA
        or any(type(value) is not bool for value in r["criteria"].values())
        or not r["zero_call_replay"]
        for r in reports
    ):
        raise ValueError("candidate lacks frozen complete-cohort provenance")
    eligible = [r for r in reports if r["status"] == "pass" and all(r["criteria"].values())]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda r: (
            -r["strict"]["strict_nfc_em"],
            -r["strict"]["strict_nfc_anls"],
            r["generation_seconds"],
            r["generation_mode"],
        ),
    )


def verify_selection(root, path, pilot_run, raw_mode):
    root = root.resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("protocol") != "phase4_label_format_selection_v1":
        raise ValueError("unknown teacher selection protocol")
    reports = []
    for relative, checksum in record["reports"].items():
        report_path = root / relative
        if sha256(report_path) != checksum:
            raise ValueError("teacher candidate report changed after selection")
        reports.append(json.loads(report_path.read_text(encoding="utf-8")))
    selected = choose(reports)
    mode = "raw_single_v1" if raw_mode else "structured_batch_v1"
    if (
        selected is None
        or record["status"] != "pass"
        or record["selected_mode"] != selected["generation_mode"]
        or record["selected_source_run"] != selected["source_run"]
        or mode != selected["generation_mode"]
        or (root / selected["source_run"]).resolve() != pilot_run.resolve()
    ):
        raise ValueError("requested teacher is not the preregistered selected candidate")
    return selected


def run(reports, output):
    values = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
    selected = choose(values)
    record = {
        "protocol": "phase4_label_format_selection_v1",
        "status": "pass" if selected else "fail",
        "selected_mode": selected["generation_mode"] if selected else None,
        "selected_source_run": selected["source_run"] if selected else None,
        "reports": {str(p): sha256(p) for p in reports},
        "candidate_metrics": {
            r["generation_mode"]: {
                "status": r["status"],
                "strict": r["strict"],
                "generation_seconds": r["generation_seconds"],
                "criteria": r["criteria"],
            }
            for r in values
        },
        "selection_rule": (
            "eligible only; EM desc, ANLS desc, total generation seconds asc; "
            "fixed before gold metrics"
        ),
        "test_ood_holdout_used_for_selection": False,
    }
    write_model(output, record)
    print(
        json.dumps({"status": record["status"], "selected_mode": record["selected_mode"]}),
        flush=True,
    )
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reports", type=Path, nargs=2, required=True)
    p.add_argument("--output", type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
