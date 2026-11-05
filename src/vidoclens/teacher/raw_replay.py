"""Replay completed raw teacher generations without constructing a model or changing targets."""

import json
from pathlib import Path

from vidoclens.contracts.local_teacher import LocalGenerationGrant
from vidoclens.contracts.raw_teacher import RawTeacherPlan
from vidoclens.contracts.silver import SilverBatch
from vidoclens.filtering.io import digest, read_model
from vidoclens.student.data import safe_path
from vidoclens.teacher.raw_labels import run_local


def replay_run(source_run, pool, images, frozen_filter=None):
    """Fixtures stay fixtures; production callers additionally reject them."""
    plan = read_model(source_run / "plan.json", RawTeacherPlan)
    grant = read_model(source_run / "grant.json", LocalGenerationGrant)
    batch = read_model(source_run / "batch.json", SilverBatch)
    manifest = json.loads((source_run / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("complete") is not True
        or manifest["batch_sha256"] != digest(batch)
        or manifest["binding"]["plan"] != digest(plan)
        or batch.pool_sha256 != digest(pool)
        or batch.fixture_only != plan.fixture_only
    ):
        raise ValueError("raw replay requires a complete checksum-bound source")

    class ReplayOnly:
        fixture_only = plan.fixture_only

        def generate(self, request, image):
            raise AssertionError("completed replay must never generate")

    environment = json.loads((source_run / "environment.json").read_text(encoding="utf-8"))
    replay, summary = run_local(
        pool,
        plan,
        grant,
        ReplayOnly(),
        images,
        environment,
        source_run,
        run_id=batch.run_id,
        max_attempts=1,
        frozen_filter=frozen_filter,
    )
    if replay != batch or summary["new_calls"]:
        raise ValueError("completed raw source does not replay exactly")
    return replay


def replay_completed(root, source_run, pool, frozen_filter=None):
    root, source_run = Path(root).resolve(), Path(source_run).resolve()
    mapping = json.loads(
        (
            root / "artifacts/phase4/teacher_protocol_v1" / f"{pool.partition}_image_map.json"
        ).read_text(encoding="utf-8")
    )
    images = {
        document: safe_path(root / "artifacts/phase4/inputs_v1", relative)
        for document, relative in mapping.items()
    }
    if read_model(source_run / "batch.json", SilverBatch).fixture_only:
        raise ValueError("synthetic labels cannot establish actual Phase4 provenance")
    return replay_run(source_run, pool, images, frozen_filter)
