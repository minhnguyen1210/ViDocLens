"""Reproducible ReceiptVQA pilot plans, from question-only loaders and frozen OCR."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.teacher import TeacherProfile, TeacherQuery, TeacherRequest
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_questions
from vidoclens.teacher.requests import canonical, chunks, digest, request_key

STRONG = "gpt-5.4-2026-03-05"
CHEAP = "gpt-5.4-mini-2026-03-17"


def make_plan(
    root: Path,
    split_dir: Path,
    archive: Path,
    train_ocr: Path,
    dev_ocr: Path,
    output: Path,
    profiles: dict[str, TeacherProfile] | None = None,
):
    """50 integration images and the same 100 dev images for all four baselines.

    No metric or gold answer is read. A5 shares the predeclared image+OCR prompt
    with A3; role selection is deferred until real dev results exist.
    """
    plan = load_frozen_plan(split_dir, 10)
    if profiles is None:
        profiles = {
            "strong": TeacherProfile(
                model_snapshot=STRONG, role="benchmark_teacher", modality="image_ocr"
            ),
            "cheap": TeacherProfile(
                model_snapshot=CHEAP, role="benchmark_teacher", modality="image_ocr"
            ),
        }
    strong, cheap = profiles["strong"].model_snapshot, profiles["cheap"].model_snapshot
    if sha256(archive) != plan.archive_sha256:
        raise ValueError("annotation archive differs from frozen plan")
    split_hash = sha256(split_dir / "summary.json")
    assignments = {a.source_image_id: a for a in plan.assignments}
    questions = defaultdict(list)
    for split in ("train", "dev"):
        for question in load_questions(archive, split=split):
            questions[question.source_image_id].append(question)
    prompt = (root / "prompts/teacher_vqa_v2.txt").read_text(encoding="utf-8")
    requests = []
    selected_manifest = []
    for directory, partition, count in ((train_ocr, "train_fit", 50), (dev_ocr, "dev_select", 100)):
        selection_file = directory / "selection.json"
        selection = json.loads(selection_file.read_text(encoding="utf-8"))
        if selection["split_summary_sha256"] != split_hash:
            raise ValueError("OCR selection belongs to another split")
        rows = [CorpusImage.model_validate(row) for row in selection["images"][:count]]
        if len(rows) != count:
            raise ValueError("not enough OCR samples for Phase 2")
        seen = set()
        variants = (
            [("pilot", "image_ocr", strong)]
            if partition == "train_fit"
            else [
                ("A1", "ocr_text", strong),
                ("A2", "image", strong),
                ("A3", "image_ocr", strong),
                ("A5", "image_ocr", cheap),
            ]
        )
        for image in rows:
            assignment = assignments[image.source_image_id]
            if assignment.partition != partition or assignment.duplicate_group_id in seen:
                raise ValueError("OCR image partition/component mismatch")
            if partition == "train_fit" and not assignment.gold_for_training:
                raise ValueError("integration pilot must use previously exposed G10 train images")
            seen.add(assignment.duplicate_group_id)
            ocr_path = directory / f"ocr_{image.source_image_id}.json"
            ocr = OCRResult.model_validate_json(ocr_path.read_text(encoding="utf-8"))
            if (
                ocr.document_id != image.document_id
                or ocr.image_sha256 != image.raw_image_sha256
                or ocr.status not in {"ok", "empty"}
            ):
                raise ValueError("OCR identity/status invalid")
            image_path = directory / "images" / f"{image.source_image_id}.jpg"
            if sha256(image_path) != image.raw_image_sha256:
                raise ValueError("materialized image bytes changed")
            text = "\n".join(
                span.text_raw for span in sorted(ocr.spans, key=lambda s: s.reading_order)
            )
            rows_q = questions[image.source_image_id]
            if len(rows_q) != image.qa_count or any(
                q.document_id != image.document_id for q in rows_q
            ):
                raise ValueError("question/image mapping mismatch")
            groups = tuple(
                chunks(tuple(TeacherQuery(qid=q.qid, question=q.question_raw) for q in rows_q))
            )
            selected_manifest.append(
                {
                    "source_image_id": image.source_image_id,
                    "partition": partition,
                    "duplicate_group_id": assignment.duplicate_group_id,
                    "image_sha256": image.raw_image_sha256,
                    "ocr_sha256": sha256(ocr_path),
                    "question_chunks": [[q.qid for q in group] for group in groups],
                }
            )
            for variant, modality, model in variants:
                for group in groups:
                    requests.append(
                        TeacherRequest(
                            archive_sha256=plan.archive_sha256,
                            split_sha256=split_hash,
                            document_id=image.document_id,
                            source_image_id=image.source_image_id,
                            partition=partition,
                            purpose="integration_pilot"
                            if partition == "train_fit"
                            else "dev_baseline",
                            experiment=variant,
                            image_sha256=image.raw_image_sha256,
                            image_path=image_path.resolve().relative_to(root.resolve()).as_posix(),
                            preprocessing="original rotated image bytes; " + image.transform_sha256,
                            ocr_text=text if modality != "image" else None,
                            ocr_sha256=sha256(ocr_path) if modality != "image" else None,
                            questions=group,
                            profile=TeacherProfile.model_validate(
                                profiles["cheap" if variant == "A5" else "strong"].model_dump()
                                | {"model_snapshot": model, "modality": modality}
                            ),
                        )
                    )
    keys = [request_key(r, prompt) for r in requests]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate request keys")
    output.mkdir(parents=True, exist_ok=False)
    with (output / "requests.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for request in requests:
            stream.write(canonical(request.model_dump(mode="json")) + "\n")
    manifest = {
        "protocol": "phase2_api_v1",
        "archive_sha256": plan.archive_sha256,
        "split_sha256": split_hash,
        "prompt_sha256": sha256(root / "prompts/teacher_vqa_v2.txt"),
        "requests_sha256": sha256(output / "requests.jsonl"),
        "request_keys": keys,
        "selection": selected_manifest,
        "counts": dict(Counter(r.experiment for r in requests)),
        "questions_per_experiment": dict(
            Counter(
                experiment for r in requests for experiment in [r.experiment] * len(r.questions)
            )
        ),
        "input_has_gold": False,
        "teacher_selected": False,
        "a5_policy": "predeclared A3 image+OCR prompt, cheaper pinned candidate",
        "selection_policy": "first50 previous G10 OCR; 100 dev seeded components; no answer access",
    }
    manifest["content_sha256"] = digest(manifest)
    write_json(output / "manifest.json", manifest)
    return manifest


def read_plan(directory: Path, root: Path):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest.pop("content_sha256")
    if (
        digest(manifest) != expected
        or sha256(directory / "requests.jsonl") != manifest["requests_sha256"]
    ):
        raise ValueError("plan checksum mismatch")
    prompt_path = root / "prompts/teacher_vqa_v2.txt"
    if sha256(prompt_path) != manifest["prompt_sha256"]:
        raise ValueError("prompt changed after plan freeze")
    prompt = prompt_path.read_text(encoding="utf-8")
    requests = [
        TeacherRequest.model_validate_json(line)
        for line in (directory / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if [request_key(r, prompt) for r in requests] != manifest["request_keys"]:
        raise ValueError("plan request identity mismatch")
    return requests, prompt, manifest
