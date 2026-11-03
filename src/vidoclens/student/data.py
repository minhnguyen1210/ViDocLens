"""Freeze G10 gold and the Phase 2 dev population, with separate label-free inputs."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from vidoclens.common.pilot import sha256, write_json
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.student import StudentConfig, StudentQuestion, StudentTrainingExample
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_questions, load_training_examples


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes workspace")
    return path


def prepare(root: Path, output: Path, config: StudentConfig):
    split_dir = root / "data/splits/receiptvqa_containment_v1"
    plan = load_frozen_plan(split_dir, 10)
    archive = root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip"
    train = load_training_examples(archive, plan)
    assignments = {a.source_image_id: a for a in plan.assignments}
    inv = root / "data/manifests/receiptvqa_ingestion_v1/images.jsonl"
    if sha256(inv) != plan.image_inventory_sha256:
        raise ValueError("inventory not bound to split")
    images = {
        r.source_image_id: r
        for r in (CorpusImage.model_validate_json(s) for s in inv.read_text().splitlines())
    }
    teacher_manifest = root / "artifacts/phase2/api_plan_v1/manifest.json"
    selection = json.loads(teacher_manifest.read_text())["selection"]
    dev_ids = {r["source_image_id"] for r in selection if r["partition"] == "dev_select"}
    if len(dev_ids) != 100 or any(assignments[i].partition != "dev_select" for i in dev_ids):
        raise ValueError("dev selection differs from frozen Phase 2 population")
    dev = [q for q in load_questions(archive, split="dev") if q.source_image_id in dev_ids]
    selected_ids = dev_ids | {r.question.source_image_id for r in train}
    output = root / output
    output.mkdir(parents=True, exist_ok=False)
    (output / "images").mkdir()
    with zipfile.ZipFile(root / "data/raw/receiptvqa/rotated_images.zip") as z:
        for i in sorted(selected_ids):
            payload = z.read(images[i].archive_member)
            if hashlib.sha256(payload).hexdigest() != images[i].raw_image_sha256:
                raise ValueError("raw image changed")
            (output / "images" / f"{i}.jpg").write_bytes(payload)

    def question(q):
        i = q.source_image_id
        return StudentQuestion(
            question=q,
            partition=assignments[i].partition,
            duplicate_group_id=assignments[i].duplicate_group_id,
            image_path=(output / "images" / f"{i}.jpg").relative_to(root).as_posix(),
            image_sha256=images[i].raw_image_sha256,
        )

    rows = {
        "train.jsonl": [
            StudentTrainingExample(input=question(r.question), answer_raw=r.reference.answers[0])
            for r in train
        ],
        "dev.jsonl": [question(q) for q in dev],
    }
    for name, records in rows.items():
        (output / name).write_text(
            "".join(canonical(r.model_dump(mode="json")) + "\n" for r in records), encoding="utf-8"
        )
    write_json(output / "config.json", config.model_dump(mode="json"))
    (output / "prompt.txt").write_bytes((root / config.prompt_path).read_bytes())
    manifest = {
        "protocol": config.protocol,
        "gold_budget": 10,
        "split_sha256": sha256(split_dir / "summary.json"),
        "archive_sha256": plan.archive_sha256,
        "dev_selection_manifest_sha256": sha256(teacher_manifest),
        "environment_lock_sha256": sha256(root / config.environment_lock),
        "files": {name: sha256(output / name) for name in (*rows, "config.json", "prompt.txt")},
        "train_qa": len(train),
        "train_images": len(selected_ids - dev_ids),
        "train_groups": len({r.input.duplicate_group_id for r in rows["train.jsonl"]}),
        "dev_qa": len(dev),
        "dev_images": len(dev_ids),
        "training_source": "authorized ReceiptVQA G10 gold only; no API outputs",
        "test_ood_calibrate_audit_used": False,
    }
    write_json(output / "manifest.json", manifest)
    load_plan(root, output)
    return manifest


def load_plan(root, directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    split_dir = root / "data/splits/receiptvqa_containment_v1"
    plan = load_frozen_plan(split_dir, 10)
    if sha256(split_dir / "summary.json") != manifest["split_sha256"]:
        raise ValueError("split changed after student plan")
    for name, checksum in manifest["files"].items():
        if sha256(safe_path(directory, name)) != checksum:
            raise ValueError("student plan file checksum mismatch")
    config = StudentConfig.model_validate_json((directory / "config.json").read_text())
    if sha256(root / config.environment_lock) != manifest["environment_lock_sha256"]:
        raise ValueError("ML lock changed")
    train = [
        StudentTrainingExample.model_validate_json(s)
        for s in (directory / "train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    dev = [
        StudentQuestion.model_validate_json(s)
        for s in (directory / "dev.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    authorized = load_training_examples(
        root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", plan
    )
    expected = {r.question.qid: (r.question, r.reference.answers[0]) for r in authorized}
    actual = {r.input.question.qid: (r.input.question, r.answer_raw) for r in train}
    if actual != expected or len(train) != len(expected):
        raise ValueError("training gold/coverage differs from authorized G10")
    assignments = {a.source_image_id: a for a in plan.assignments}
    inv = root / "data/manifests/receiptvqa_ingestion_v1/images.jsonl"
    if sha256(inv) != plan.image_inventory_sha256:
        raise ValueError("frozen inventory changed")
    images = {
        r.source_image_id: r
        for r in (CorpusImage.model_validate_json(s) for s in inv.read_text().splitlines())
    }
    teacher_manifest = root / "artifacts/phase2/api_plan_v1/manifest.json"
    if sha256(teacher_manifest) != manifest["dev_selection_manifest_sha256"]:
        raise ValueError("dev selection changed")
    dev_ids = {
        r["source_image_id"]
        for r in json.loads(teacher_manifest.read_text())["selection"]
        if r["partition"] == "dev_select"
    }
    permitted_dev = {
        q.qid: q
        for q in load_questions(
            root / "data/raw/receiptvqa/ReceiptVQA_annotations.zip", split="dev"
        )
        if q.source_image_id in dev_ids
    }
    if {r.question.qid: r.question for r in dev} != permitted_dev:
        raise ValueError("dev questions differ from selected frozen population")
    for row in [r.input for r in train] + dev:
        assignment = assignments[row.question.source_image_id]
        if (row.partition, row.duplicate_group_id) != (
            assignment.partition,
            assignment.duplicate_group_id,
        ):
            raise ValueError("student membership differs from split")
        if row.image_sha256 != images[row.question.source_image_id].raw_image_sha256:
            raise ValueError("student image hash differs from inventory")
    if len({q.question.qid for q in dev}) != len(dev) or any(
        q.partition != "dev_select" for q in dev
    ):
        raise ValueError("invalid dev population")
    return config, train, dev, manifest


def epoch_order(count, seed, epoch):
    import random

    order = list(range(count))
    random.Random(seed + 1000003 * epoch).shuffle(order)
    return order


def smoke_indices(rows, count=64):
    # Train gold only: include longest answers/questions, plus deterministic coverage.
    ranked = sorted(
        range(len(rows)),
        key=lambda i: (
            -len(rows[i].answer_raw),
            -len(rows[i].input.question.question_raw),
            rows[i].input.question.qid,
        ),
    )
    selected = ranked[:16]
    for i in sorted(
        range(len(rows)),
        key=lambda i: hashlib.sha256(rows[i].input.question.qid.encode()).hexdigest(),
    ):
        if i not in selected:
            selected.append(i)
        if len(selected) >= count:
            break
    return selected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    a = p.parse_args()
    result = prepare(
        a.root.resolve(), a.output, StudentConfig.model_validate_json(a.config.read_text())
    )
    print(canonical({k: v for k, v in result.items() if k != "files"}))


if __name__ == "__main__":
    main()
