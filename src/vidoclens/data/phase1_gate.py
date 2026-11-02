"""Verify the AI-assisted G1 evidence chain (ADR-021); never promote it to human gold."""

import argparse
import hashlib
import json
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.ai_review import (
    AIAdjudication,
    AIReviewOutput,
    OODSeedDocument,
    OODSeedQA,
)
from vidoclens.contracts.review import TranscriptionReview
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.local_ai_review import load_tasks
from vidoclens.data.ood_seed import local_file
from vidoclens.eval.transcription import evaluate_reviews


def record_hash(record) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


def validate_seed(documents, annotations):
    by_id = {doc.document_id: doc for doc in documents}
    if len(by_id) != len(documents) or len({q.qid for q in annotations}) != len(annotations):
        raise ValueError("duplicate seed identity")
    for qa in annotations:
        doc = by_id.get(qa.document_id)
        if (
            doc is None
            or doc.partition != "ood_seed"
            or qa.image_sha256 != doc.processed_image_sha256
            or qa.rights_evidence_id != doc.rights_evidence_id
            or qa.shift_axes != doc.shift_axes
            or qa.second_review != "ai_only"
        ):
            raise ValueError("unreviewed, quarantined or unbound seed annotation")
    if {q.document_id for q in annotations} != by_id.keys():
        raise ValueError("every seed image needs annotations")


def validate_review(tasks, outputs, adjudications, final_hashes):
    """Require explicit image adjudication, even if a reviewer happens to agree."""
    inputs = {t.task_id: t for t in tasks}
    results = {o.task_id: o for o in outputs}
    decisions = {a.task_id: a for a in adjudications}
    if (
        len(inputs) != len(tasks)
        or len(results) != len(outputs)
        or len(decisions) != len(adjudications)
    ):
        raise ValueError("duplicate review identities")
    if inputs.keys() != results.keys() or inputs.keys() != decisions.keys():
        raise ValueError("incomplete review/adjudication")
    successful = set()
    for task_id, task in inputs.items():
        result, decision = results[task_id], decisions[task_id]
        if result.input_image_sha256 != task.image_sha256:
            raise ValueError("review output used another image")
        if decision.final_record_sha256 != final_hashes.get(task_id):
            raise ValueError("adjudication does not bind the final reference")
        if decision.decision == "uncertain_excluded":
            raise ValueError("unresolved reference still present in final task set")
        if result.status == "ok" and not result.truncated and result.raw_text.strip():
            successful.add(task_id)
    return successful


def require_coverage(documents, annotations, tasks, successful, cer):
    ood_ids = {q.qid for q in annotations}
    ocr = [t for t in tasks if t.kind == "ocr_transcription" and t.task_id in successful]
    checked_ood = ood_ids & successful
    if len(documents) < 3 or len(annotations) < 18 or len(checked_ood) / len(annotations) < 0.2:
        raise ValueError("OOD seed/review coverage below ADR-021")
    if len({t.document_id for t in ocr}) < 3 or len(ocr) < 30:
        raise ValueError("OCR second-pass coverage below ADR-021")
    if cer["documents"] < 3 or cer["by_reviewer_type"].get("ai", {}).get("lines", 0) < 30:
        raise ValueError("insufficient image transcription/CER evidence")
    return {
        "ood_images": len(documents),
        "ood_qa": len(annotations),
        "ood_qa_second_ai_reviewed": len(checked_ood),
        "ocr_second_ai_reviewed_lines": len(ocr),
    }


def run(root: Path, final_dir: Path, output: Path):
    root = root.resolve()
    evidence = {}

    def bound(path, expected=None):
        file = path if path.is_absolute() else root / path
        file = local_file(root, str(file))
        actual = sha256(file)
        if expected is not None and actual != expected:
            raise ValueError(f"evidence checksum mismatch: {file.name}")
        evidence[file.relative_to(root).as_posix()] = actual
        return file

    def read(path):
        return json.loads(bound(path).read_text(encoding="utf-8"))

    seed = Path("data/manifests/commons_ood_seed_v1")
    seed_summary = read(seed / "summary.json")
    if seed_summary["status"] != "pass" or seed_summary["candidate_edges"] != 0:
        raise ValueError("OOD overlaps must be contained before admitting seed")
    for name, key in (
        ("documents.jsonl", "documents_sha256"),
        ("overlap.json", "overlap_sha256"),
        ("graph_extension.json", "graph_extension_sha256"),
    ):
        bound(seed / name, seed_summary[key])
    bound(
        Path("data/manifests/receiptvqa_ingestion_v1/images.jsonl"),
        seed_summary["inventory_sha256"],
    )
    bound(
        Path("data/manifests/receiptvqa_features_v1/features.jsonl"),
        seed_summary["features_sha256"],
    )
    extension = read(seed / "graph_extension.json")
    bound(Path(extension["base_graph_path"]), extension["base_graph_sha256"])
    documents = [
        OODSeedDocument.model_validate_json(line)
        for line in (root / seed / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if extension["candidate_edges"] or extension["permissions"] != {
        d.document_id: "ood_seed" for d in documents
    }:
        raise ValueError("seed graph permissions mismatch")
    for doc in documents:
        for path, digest in (
            (doc.raw_path, doc.raw_image_sha256),
            (doc.image_path, doc.processed_image_sha256),
            (doc.metadata_path, doc.metadata_sha256),
        ):
            bound(Path(path), digest)
    annotations_file = bound(final_dir / "ood_annotations.jsonl")
    annotations = [
        OODSeedQA.model_validate_json(line)
        for line in annotations_file.read_text(encoding="utf-8").splitlines()
    ]
    validate_seed(documents, annotations)
    final_hashes = {qa.qid: record_hash(qa) for qa in annotations}
    review_files = sorted((root / final_dir).glob("review_*.json"))
    for file in review_files:
        bound(file)
        review = TranscriptionReview.model_validate_json(file.read_text(encoding="utf-8"))
        if review.reviewer_type != "ai" or review.human_verified:
            raise ValueError("unexpected reviewer provenance")
        for line in review.lines:
            if line.legibility == "readable":
                final_hashes[review.document_id + ":transcription:" + line.line_id] = sha256(file)
    cer = evaluate_reviews(review_files, root / "artifacts/phase1/ocr_quality_v1")
    provenance = read(final_dir / "provenance.json")
    bound(final_dir / "ood_annotations.jsonl", provenance["final_ood_sha256"])
    bound(final_dir / "adjudications.jsonl", provenance["adjudications_sha256"])
    initial = Path("artifacts/phase1/ai_closure_inputs_v1")
    bound(initial / "ood_draft.jsonl", provenance["initial_draft_sha256"])
    bound(initial / "provenance.json", provenance["input_provenance_sha256"])
    review_dir = Path(provenance["local_review_dir"])
    summary = read(review_dir / "summary.json")
    if (
        summary["status"] != "completed"
        or summary["auto_accept_labels"]
        or summary["model_accuracy_evaluated"]
    ):
        raise ValueError("invalid annotation review run")
    profile = read(review_dir / "profile.json")
    bound(review_dir / "source.py")
    bound(review_dir / "environment.json")
    tasks_file = bound(review_dir / "input_tasks.jsonl", profile["input_tasks_sha256"])
    tasks = load_tasks(root, tasks_file)
    qa_by_id = {q.qid: q for q in annotations}
    for task in tasks:
        if task.kind == "ood_annotation_check":
            qa = qa_by_id.get(task.task_id)
            if (
                qa is None
                or task.question != qa.question
                or task.document_id != qa.document_id
                or task.image_sha256 != qa.image_sha256
            ):
                raise ValueError("OOD reviewer question/identity changed")
    if profile["labels_or_ocr_in_input"]:
        raise ValueError("reviewer inputs must be reference-free")
    outputs, output_hashes = [], {}
    for row in summary["outputs"]:
        file = bound(review_dir / row["file"], row["sha256"])
        result = AIReviewOutput.model_validate_json(file.read_text(encoding="utf-8"))
        if result.task_id != row["task_id"]:
            raise ValueError("output task identity mismatch")
        outputs.append(result)
        output_hashes[result.task_id] = row["sha256"]
    adjudication_file = bound(final_dir / "adjudications.jsonl")
    decisions = [
        AIAdjudication.model_validate_json(line)
        for line in adjudication_file.read_text(encoding="utf-8").splitlines()
    ]
    if any(a.reviewer_output_sha256 != output_hashes.get(a.task_id) for a in decisions):
        raise ValueError("adjudication reviewer checksum mismatch")
    successful = validate_review(tasks, outputs, decisions, final_hashes)
    counts = require_coverage(documents, annotations, tasks, successful, cer)
    frozen = root / "data/splits/receiptvqa_containment_v1"
    for budget in (5, 10, 25, 100):
        load_frozen_plan(frozen, budget)
    frozen_summary = read(frozen / "summary.json")
    for name, digest in frozen_summary["files"].items():
        bound(frozen / name, digest)
    split = read(Path("artifacts/phase1/frozen_split_verification_v1.json"))
    bound(frozen / "summary.json", split["split_summary_sha256"])
    if (
        split["uncontained_edges"]
        or split["test_gold_read"]
        or split["silver_contains_gold_fields"]
    ):
        raise ValueError("data boundary audit failed")
    parity = read(Path("artifacts/phase1/upstream_parity_v1/parity_report.json"))
    for name, digest in parity["upstream_files"].items():
        bound(Path("artifacts/phase1/upstream_parity_v1") / name, digest)
    oracle = read(Path("artifacts/phase1/r1_oracle_v1/report.json"))
    if parity["status"] != "pass" or oracle["status"] != "pass" or oracle["test_or_ood_evaluated"]:
        raise ValueError("metric/oracle evidence is not valid")
    report = {
        "status": "pass",
        "phase1_complete": True,
        "protocol": "g1_ai_review_v1",
        "scope_authority": "user explicit AI-only instruction; SOT 7.5 / ADR-021",
        **counts,
        "cer": cer,
        "ood_answerable": sum(q.answerable for q in annotations),
        "human_gold_available": False,
        "final_ood_benchmark_ready": False,
        "paid_api_calls": 0,
        "test_gold_opened": False,
        "evidence_sha256": evidence,
    }
    write_json(output, report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"evidence_sha256", "cer"}}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "final-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
