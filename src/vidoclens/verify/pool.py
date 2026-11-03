"""Separate Phase 5 dev access; Phase 4's calibration exclusion stays unchanged."""

from vidoclens.common.pilot import sha256
from vidoclens.contracts.ingestion import CorpusImage
from vidoclens.contracts.silver import SilverSample
from vidoclens.contracts.verification import VerificationPool
from vidoclens.data.freeze import load_frozen_plan
from vidoclens.data.receiptvqa import load_questions
from vidoclens.filtering.io import digest, revalidate
from vidoclens.verify.verifier import implementation_hash


def require_profile(pool, profile):
    pool, profile = revalidate(pool), revalidate(profile)
    if profile.implementation_sha256 != implementation_hash():
        raise ValueError("verifier implementation changed; select and freeze a new profile")
    if pool.access_plan_sha256 != profile.access_plan_sha256:
        raise ValueError("profile belongs to another frozen access plan")
    if pool.partition == "dev_calibrate" and profile.status != "frozen_dev_select":
        raise PermissionError("freeze model/filter/verifier before calibration access")


def make_pool(archive, frozen, inventory, partition, *, profile=None):
    if partition not in {"dev_select", "dev_calibrate"}:
        raise PermissionError("Phase 5 tooling only opens dev_select/dev_calibrate")
    if profile is not None and revalidate(profile).implementation_sha256 != implementation_hash():
        raise ValueError("verifier implementation changed; freeze before reading calibration data")
    if partition == "dev_calibrate" and (
        profile is None or revalidate(profile).status != "frozen_dev_select"
    ):
        raise PermissionError("dev_calibrate requires frozen verifier profile before reading data")
    plan = load_frozen_plan(frozen, 10)
    if sha256(archive) != plan.archive_sha256 or sha256(inventory) != plan.image_inventory_sha256:
        raise ValueError("source hashes differ from frozen plan")
    if profile is not None and profile.access_plan_sha256 != digest(plan):
        raise ValueError("profile access plan mismatch")
    images = [
        CorpusImage.model_validate_json(line)
        for line in inventory.read_text(encoding="utf-8").splitlines()
    ]
    by_image = {r.source_image_id: r for r in images}
    assignments = {r.source_image_id: r for r in plan.assignments}
    if len(by_image) != len(images) or by_image.keys() != assignments.keys():
        raise ValueError("inventory must cover the frozen corpus exactly")
    samples = []
    for q in load_questions(archive, split="dev"):
        entry, im = assignments[q.source_image_id], by_image[q.source_image_id]
        if (
            im.document_id != q.document_id
            or im.source_split != "dev"
            or entry.source_split != "dev"
            or im.annotation_filename != q.filename
        ):
            raise ValueError("question/image identity mismatch")
        if entry.partition == partition:
            samples.append(
                SilverSample(
                    question=q,
                    duplicate_group_id=entry.duplicate_group_id,
                    image_sha256=im.raw_image_sha256,
                )
            )
    pool = VerificationPool(
        partition=partition,
        archive_sha256=plan.archive_sha256,
        access_plan_sha256=digest(plan),
        inventory_sha256=sha256(inventory),
        samples=tuple(sorted(samples, key=lambda s: s.question.qid)),
    )
    if profile is not None:
        require_profile(pool, profile)
    return pool
