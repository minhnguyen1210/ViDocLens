"""Render measured Phase 4 evidence as Markdown; incomplete gates remain incomplete."""

import argparse
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.distillation import Phase4GateReport
from vidoclens.filtering.io import read_model, write_text_exclusive


def percent(value):
    return "—" if value is None else f"{100 * value:.2f}%"


def report(root, execution, gate_path, output):
    root = root.resolve()
    execution, gate_path, output = (root / p for p in (execution, gate_path, output))
    gate = read_model(gate_path, Phase4GateReport)
    criteria = gate.criteria.model_dump(exclude={"schema_version", "human_error_review"})
    if not all(criteria.values()):
        raise ValueError("a results report requires every machine evidence gate")
    for name, checksum in gate.evidence.items():
        path = root / name
        if not path.is_file() or sha256(path) != checksum:
            raise ValueError("G4 evidence changed after audit")

    def bound(name):
        path = execution / name
        if str(path) not in gate.evidence:
            raise ValueError("report input was not bound by G4: " + name)
        return json.loads(path.read_text(encoding="utf-8"))

    pilot = bound("pilot_report.json")
    filtering = bound("labeling/freeze/config.json")
    holdout = bound("holdout_report.json")
    comparison = bound("comparison/comparison.json")
    label_runs = {
        partition: bound(partition + "_teacher/manifest.json")
        for partition in ("train_fit", "audit_holdout")
    }
    if (
        comparison["fixture_only"]
        or holdout["fixture_only"]
        or len(comparison["runs"]) != 12
        or pilot["strict"]["n_questions"] != 666
        or not math.isclose(
            gate.h2_primary_difference,
            comparison["paired_em"]["P2_vs_P1-size"]["training_seed_delta_mean"],
            abs_tol=1e-12,
        )
    ):
        raise ValueError("report population/provenance differs from the actual gate")
    if any(not run["complete"] or run["fixture_only"] for run in label_runs.values()):
        raise ValueError("label-generation cost requires completed real manifests")

    def link(label, path):
        relative = Path(os.path.relpath(path, output.parent)).as_posix()
        return f"[{label}](<{relative}>)"

    lines = [
        "# Kết quả Phase 4 — ViDocLens",
        "",
        f"Tạo từ evidence ngày {datetime.now(UTC).isoformat()}. G4: **{gate.status}**.",
        "",
        "G4 đã đạt đủ các tiêu chí, gồm human review thật."
        if gate.status == "pass"
        else "**G4 chưa hoàn tất:** còn human review thật. Các kết quả máy dưới đây đã qua audit.",
        "",
        "## Phạm vi và bảo toàn",
        "",
        "Giữ nguyên G3, artifacts và frozen split Phase 3; L2 được adopt từ evidence cũ. "
        "Dev có 100 components/666 QA. Silver train ngoài G10 có 4.073 ảnh/27.774 QA; "
        "audit holdout có 504 ảnh/3.454 QA. Test, OOD và dev_calibrate không được dùng "
        "để chọn teacher, filter, checkpoint hoặc huấn luyện trong Phase 4.",
        "",
        "## Teacher local",
        "",
        f"Model `{pilot['generation_config']['model_id']}`, revision "
        f"`{pilot['generation_config']['model_revision']}`; image + question, "
        "không có gold trong input. Dùng cùng teacher/pool cho các silver arms.",
        "",
        f"Candidate được chọn: `{pilot['generation_mode']}`; strict EM "
        f"{percent(pilot['strict']['strict_nfc_em'])}, ANLS "
        f"{percent(pilot['strict']['strict_nfc_anls'])}, coverage "
        f"{percent(pilot['strict']['coverage'])}. Generation "
        f"{pilot['generation_seconds'] / 60:.2f} phút; peak reserved "
        f"{pilot['peak_reserved_bytes'] / 1024**3:.3f} GiB. "
        "Đây là gate khả thi, không chứng minh teacher vượt L2; giữ nguyên failure "
        "và raw output. Thời gian là generation trên host dùng chung.",
        "",
        "| Sinh nhãn | QA | Requests | Answered | Generation phút đã đo | "
        "Requests thiếu số đo | Peak reserved GiB |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, run in label_runs.items():
        requests = run["requests"]
        times = [
            r["generation_seconds"] for r in requests if r.get("generation_seconds") is not None
        ]
        peaks = [
            r["peak_reserved_bytes"] for r in requests if r.get("peak_reserved_bytes") is not None
        ]
        peak = f"{max(peaks) / 1024**3:.3f}" if peaks else "—"
        lines.append(
            f"| {name} | {sum(run['label_status_counts'].values())} | {len(requests)} | "
            f"{run['label_status_counts'].get('answered', 0)} | {sum(times) / 60:.2f} | "
            f"{len(requests) - len(times)} | {peak} |"
        )
    lines += [
        "",
        "Thời gian sinh nhãn lấy từ từng request trong manifest, không gồm load weights, "
        "OCR, I/O, pilot thất bại hoặc retries ngoài các run này. Không gọi đây là tổng "
        "wall time hay chi phí toàn dự án. Logs/cost của các lần chạy dở giữ trong "
        f"{link('STATUS_HISTORY', root / 'docs/STATUS_HISTORY.md')}.",
        "",
        "## Filter và audit holdout",
        "",
        f"F1 đã freeze trên dev: tau={filtering['text_max_normalized_edit_distance']}, "
        f"tối đa {filtering['max_consecutive_lines']} dòng; không sửa digit/target. "
        "Không thay rule theo holdout hoặc kết quả H2.",
        "",
        "| Population | QA | Eligible | Kept | Precision | Recall | Retention | "
        "False accept | False reject |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def rates(name, row):
        return (
            f"| {name.replace('|', '/')} | {row['requested']} | {row['eligible']} | "
            f"{row['kept']} | {percent(row['filter_precision'])} | "
            f"{percent(row['filter_recall'])} | {percent(row['retention'])} | "
            f"{row['false_accept']} | {row['false_reject']} |"
        )

    lines.append(rates("Toàn audit holdout", holdout["overall"]))
    for axis in ("by_answer_type", "by_question_type", "ocr_quality_bins"):
        for name, row in (holdout.get(axis) or {}).items():
            lines.append(rates(f"{axis}: {name}", row))
    lines += [
        "",
        "OCR confidence bins là proxy của engine, không phải CER hoặc human quality. "
        "OCR agreement không chứng nhận đáp án đúng nghĩa trường được hỏi.",
        "",
        "## Student: mean và sample SD qua ba seed",
        "",
        "| Arm | Strict EM mean ± SD | Token F1 mean ± SD | ANLS mean ± SD |",
        "|---|---:|---:|---:|",
    ]
    for arm in ("L2", "P1-full", "P1-size", "P2"):
        values = comparison["seed_summary"][arm]
        cells = [
            f"{100 * values[m]['mean']:.2f}% ± {100 * values[m]['sample_std']:.2f} pp"
            for m in ("strict_nfc_em", "strict_nfc_token_f1", "strict_nfc_anls")
        ]
        lines.append("| " + " | ".join([arm, *cells]) + " |")
    lines += [
        "",
        "| Arm | Seed | Checkpoint step | Strict EM | Training phút | Peak reserved GiB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["runs"].values():
        lines.append(
            f"| {row['arm']} | {row['seed']} | {row['selected_checkpoint_step']} | "
            f"{percent(row['metrics']['strict_nfc_em'])} | "
            f"{row['training_seconds'] / 60:.2f} | {row['peak_reserved_bytes'] / 1024**3:.3f} |"
        )
    lines += [
        "",
        "Mọi primary run có 191 updates. Silver arms có 1.528 gold + 1.528 silver "
        "exposures; L2 lịch sử có 3.053 gold exposures. Primary P2/P1-size khớp updates, "
        "hyperparameters, gold order/counts và số silver samples; FLOPs/wall time "
        "có thể khác theo ảnh/target. Checkpoint được chọn riêng mỗi seed từ step96/191; "
        "không chọn seed tốt nhất. Chi phí bảng trên là toàn trajectory, không chỉ "
        "prefix của checkpoint được chọn; không gồm label/OCR/load/eval/save.",
        "",
        "## H2: paired group bootstrap",
        "",
        "| So sánh | Mean delta EM (pp) | Seed delta SD (pp) | 95% group CI (pp) |",
        "|---|---:|---:|---|",
    ]
    for name, row in comparison["paired_em"].items():
        ci = row["fixed_three_seed_mean_group_bootstrap"]
        interval = (
            "Không đủ groups"
            if ci["lower_95"] is None
            else f"[{100 * ci['lower_95']:.2f}; {100 * ci['upper_95']:.2f}]"
        )
        lines.append(
            f"| {name} | {100 * row['training_seed_delta_mean']:+.2f} | "
            f"{100 * row['training_seed_delta_sample_std']:.2f} | {interval} |"
        )
    primary_ci = comparison["paired_em"]["P2_vs_P1-size"]["fixed_three_seed_mean_group_bootstrap"]
    if primary_ci["lower_95"] is None:
        interpretation = "Chưa đủ groups để kết luận H2 bằng khoảng tin cậy."
    elif primary_ci["lower_95"] > 0:
        interpretation = (
            "P2 cải thiện EM so với P1-size trên dev; CI conditional theo ba seed nằm trên 0."
        )
    elif primary_ci["upper_95"] < 0:
        interpretation = (
            "P2 giảm EM so với P1-size trên dev; kết quả hiện tại không ủng hộ lợi ích H2."
        )
    else:
        interpretation = (
            "CI primary chứa 0; bằng chứng dev hiện tại chưa phân biệt rõ lợi ích "
            "của P2 so với P1-size."
        )
    lines += [
        "",
        interpretation,
        "",
        f"Primary P2−P1-size: {100 * gate.h2_primary_difference:+.2f} điểm EM trên dev. "
        "Đọc ước lượng cùng CI và seed SD ở trên. CI bootstrap theo duplicate group "
        "với 2.000 resamples, conditional trên ba seed đã chạy; không bao gồm training "
        "variance. Đây là dev selection, chưa là xác nhận final test. H2 âm vẫn là "
        "kết quả hợp lệ nếu đủ evidence; không đổi filter để làm H2 thắng.",
        "",
        "## Human review và evidence",
        "",
        "Human review đã được gate kiểm đủ packet và attestation."
        if gate.criteria.human_error_review
        else "Human review còn thiếu; không được ghi Phase 4/G4 đã hoàn tất.",
        "",
        " · ".join(
            link(label, path)
            for label, path in (
                ("G4 report", gate_path),
                ("Comparison và slices", execution / "comparison/comparison.json"),
                ("Holdout audit", execution / "holdout_report.json"),
                ("Resume proof", execution / "campaign/resume_proof.json"),
                ("STATUS", root / "docs/STATUS.md"),
            )
        ),
        "",
        f"G4 report SHA-256: `{sha256(gate_path)}`. Không suy CI, release hoặc "
        "API readiness từ kết quả local này. Assistant không stage/commit/push.",
        "",
    ]
    human_summary = gate_path.with_name(gate_path.stem + "_human_review.json")
    if gate.criteria.human_error_review and human_summary.is_file():
        lines += [link("Human review theo bốn strata", human_summary), ""]
    output.parent.mkdir(parents=True, exist_ok=True)
    write_text_exclusive(output, "\n".join(lines))
    return {"gate_status": gate.status, "output": str(output), "sha256": sha256(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    for name in ("execution", "gate-path", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    print(json.dumps(report(**vars(parser.parse_args()))))


if __name__ == "__main__":
    main()
