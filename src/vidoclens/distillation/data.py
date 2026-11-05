"""Validate real silver provenance and join it with the unchanged authorized G10 loader."""

import argparse
import json
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.contracts.distillation import (
    DistillationConfig,
    DistillationExample,
    DistillationPlan,
)
from vidoclens.contracts.silver import (
    FilterRun,
    SilverApproval,
    SilverBatch,
    SilverExperiment,
    SilverPool,
)
from vidoclens.contracts.student import StudentQuestion
from vidoclens.distillation.inputs import COHORT_SHA256, g3_evidence, source_paths
from vidoclens.filtering.bundle import FILES, load_bundle
from vidoclens.filtering.experiments import select_experiments
from vidoclens.filtering.io import digest, read_model, write_model, write_text_exclusive
from vidoclens.filtering.pool import make_pool
from vidoclens.student.data import load_plan as load_gold_plan
from vidoclens.student.data import safe_path


def implementation_files(root):
    paths = (root / "src/vidoclens").rglob("*.py")
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(paths)}


def profile(root):
    _, cohort = g3_evidence(root)
    config, _, _, _ = load_gold_plan(root, root / "artifacts/phase3/data_v2")
    return DistillationConfig(
        student=config,
        evaluation_cohort_sha256=sha256(cohort),
        g3_evidence_sha256=sha256(root / "artifacts/phase3/g3_report_v1.json"),
    )


def prepare(root, bundle, approval_path, inputs, output):
    root = root.resolve()
    bundle, approval_path, inputs, output = (
        root / p for p in (bundle, approval_path, inputs, output)
    )
    recipe = profile(root)
    pool, batch, filtered = load_bundle(bundle)
    if batch.fixture_only:
        raise PermissionError("synthetic labels cannot enter real student training")
    if digest(pool) != digest(make_pool(*source_paths(root), "train_fit")):
        raise ValueError("training pool differs from frozen source")
    approval = read_model(approval_path, SilverApproval)
    base, gold, dev, gold_manifest = load_gold_plan(root, root / "artifacts/phase3/data_v2")
    evaluation = read_model(inputs / "dev_select.json", SilverPool)
    if evaluation.evaluation_cohort_sha256 != COHORT_SHA256 or {r.question.qid for r in dev} != {
        s.question.qid for s in evaluation.samples
    }:
        raise ValueError("evaluation must preserve Phase 3 cohort")
    output.mkdir(parents=True, exist_ok=False)
    write_model(output / "training_profile.json", recipe)
    profile_hash = sha256(output / "training_profile.json")
    selections = select_experiments(pool, batch, filtered, approval, profile_hash, 191)
    samples = {s.question.qid: s for s in pool.samples}
    labels = {s.qid: s for s in batch.labels}
    image_map = json.loads((inputs / "image_map.json").read_text(encoding="utf-8"))
    dependencies = {
        p.relative_to(root).as_posix(): sha256(p)
        for p in [
            *(bundle / n for n in FILES | {"manifest.json"}),
            approval_path,
            inputs / "dev_select.json",
            inputs / "image_map.json",
            root / "artifacts/phase3/g3_report_v1.json",
            root / "artifacts/phase3/data_v2/manifest.json",
            root / "artifacts/phase3/dev_protocol_v2.json",
        ]
    }
    sources = implementation_files(root)
    for selection in selections:
        directory = output / f"{selection.arm}-{selection.seed}"
        directory.mkdir()
        records = [DistillationExample(**r.model_dump(), source="gold") for r in gold]
        for qid in selection.silver_qids:
            s, label = samples[qid], labels[qid]
            if label.status != "answered":
                raise ValueError("selected silver is not an answered teacher target")
            image = safe_path(inputs, image_map[s.question.document_id])
            if sha256(image) != s.image_sha256:
                raise ValueError("silver image differs from frozen source")
            records.append(
                DistillationExample(
                    source="silver",
                    answer_raw=label.answer_raw,
                    input=StudentQuestion(
                        question=s.question,
                        partition="train_fit",
                        duplicate_group_id=s.duplicate_group_id,
                        image_path=image.relative_to(root).as_posix(),
                        image_sha256=s.image_sha256,
                    ),
                )
            )
        write_text_exclusive(
            directory / "train.jsonl", "".join(r.model_dump_json() + "\n" for r in records)
        )
        write_text_exclusive(
            directory / "dev.jsonl", "".join(r.model_dump_json() + "\n" for r in dev)
        )
        write_text_exclusive(
            directory / "prompt.txt", (root / base.prompt_path).read_text(encoding="utf-8")
        )
        write_model(directory / "config.json", base)
        write_model(directory / "selection.json", selection)
        write_model(directory / "profile.json", recipe)
        manifest = DistillationPlan(
            arm=selection.arm,
            seed=selection.seed,
            split_sha256=gold_manifest["split_sha256"],
            environment_lock_sha256=gold_manifest["environment_lock_sha256"],
            g3_evidence_sha256=recipe.g3_evidence_sha256,
            selection_sha256=digest(selection),
            training_profile_sha256=profile_hash,
            evaluation_pool_sha256=digest(evaluation),
            bundle_path=bundle.relative_to(root).as_posix(),
            approval_path=approval_path.relative_to(root).as_posix(),
            files={p.name: sha256(p) for p in directory.iterdir()},
            dependencies=dependencies,
            source_hashes=sources,
            gold_qa=len(gold),
            silver_qa=len(selection.silver_qids),
            dev_qa=len(dev),
        )
        write_model(directory / "manifest.json", manifest)
        protocol = json.loads(
            (root / "artifacts/phase3/dev_protocol_v2.json").read_text(encoding="utf-8")
        )
        protocol["plan_sha256"] = sha256(directory / "manifest.json")
        write_model(directory / "dev_protocol.json", protocol)
    write_model(
        output / "manifest.json",
        {
            "complete": True,
            "training_executed": False,
            "plans": {
                f"{s.arm}-{s.seed}": sha256(output / f"{s.arm}-{s.seed}" / "manifest.json")
                for s in selections
            },
        },
    )
    return selections


def load_plan(root, directory):
    manifest = read_model(directory / "manifest.json", DistillationPlan)
    if manifest.source_hashes != implementation_files(root):
        raise ValueError("distillation implementation changed after plan freeze")
    for base, files in (
        (directory, manifest.files),
        (root, manifest.dependencies),
        (root, manifest.source_hashes),
    ):
        for name, checksum in files.items():
            if sha256(safe_path(base, name)) != checksum:
                raise ValueError("distillation input/dependency/source checksum mismatch")
    recipe = read_model(directory / "profile.json", DistillationConfig)
    if sha256(directory / "profile.json") != manifest.training_profile_sha256 or recipe != profile(
        root
    ):
        raise ValueError("distillation recipe differs from validated Phase 3 settings")
    selection = read_model(directory / "selection.json", SilverExperiment)
    pool = read_model(safe_path(root, manifest.bundle_path) / "pool.json", SilverPool)
    batch = read_model(safe_path(root, manifest.bundle_path) / "batch.json", SilverBatch)
    filtered = read_model(safe_path(root, manifest.bundle_path) / "run.json", FilterRun)
    approval = read_model(safe_path(root, manifest.approval_path), SilverApproval)
    expected = select_experiments(
        pool, batch, filtered, approval, manifest.training_profile_sha256, 191
    )
    if (
        batch.fixture_only
        or selection not in expected
        or digest(selection) != manifest.selection_sha256
    ):
        raise ValueError("real training selection/permission mismatch")
    base, gold, dev, gold_manifest = load_gold_plan(root, root / "artifacts/phase3/data_v2")
    rows = [
        DistillationExample.model_validate_json(s)
        for s in (directory / "train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    gold_expected = {r.input.question.qid: (r.input, r.answer_raw) for r in gold}
    gold_actual = {
        r.input.question.qid: (r.input, r.answer_raw) for r in rows if r.source == "gold"
    }
    silver_actual = {r.input.question.qid: r for r in rows if r.source == "silver"}
    targets = {r.qid: r.answer_raw for r in batch.labels if r.status == "answered"}
    samples = {r.question.qid: r for r in pool.samples}
    if (
        gold_actual != gold_expected
        or len(rows) != len(gold_actual) + len(silver_actual)
        or set(silver_actual) != set(selection.silver_qids)
        or len(silver_actual) != manifest.silver_qa
        or len(gold_actual) != manifest.gold_qa
    ):
        raise ValueError("raw gold/silver training population mismatch")
    for qid, row in silver_actual.items():
        s = samples[qid]
        if (
            row.answer_raw != targets[qid]
            or row.input.question != s.question
            or row.input.duplicate_group_id != s.duplicate_group_id
            or row.input.image_sha256 != s.image_sha256
        ):
            raise ValueError("silver target/image/group changed after filtering")
    actual_dev = [
        StudentQuestion.model_validate_json(s)
        for s in (directory / "dev.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if actual_dev != dev or manifest.split_sha256 != gold_manifest["split_sha256"]:
        raise ValueError("Phase 3 dev population/split changed")
    if (manifest.arm, manifest.seed) != (selection.arm, selection.seed):
        raise ValueError("arm/seed mismatch")
    return base, rows, dev, manifest.model_dump(mode="json")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    for name in ("bundle", "approval-path", "inputs", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    prepare(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
