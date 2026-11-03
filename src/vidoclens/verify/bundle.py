"""Immutable CPU verification bundles, replayable without gold or a loaded model."""

import json

from vidoclens.common.pilot import sha256
from vidoclens.contracts.evaluation import AnswerPrediction
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.verification import (
    VerificationBatch,
    VerificationPool,
    VerifierInput,
    VerifierProfile,
)
from vidoclens.filtering.io import digest, read_model, revalidate, write_model
from vidoclens.verify.pool import require_profile
from vidoclens.verify.verifier import verify

FILES = {"pool.json", "student.json", "profile.json", "ocr.json", "decisions.json"}


def check_batch(pool, batch, profile):
    pool, batch, profile = revalidate(pool), revalidate(batch), revalidate(profile)
    require_profile(pool, profile)
    if batch.pool_sha256 != digest(pool) or digest(batch.binding) != digest(profile.binding):
        raise ValueError("prediction batch pool/binding mismatch")
    known = {s.question.qid for s in pool.samples}
    if any(o.prediction.qid not in known for o in batch.observations):
        raise ValueError("unknown prediction qid")
    return pool, batch, profile


def decisions(pool, batch, ocr, profile):
    pool, batch, profile = check_batch(pool, batch, profile)
    ocr = [OCRResult.model_validate(r.model_dump()) for r in ocr]
    documents = {s.question.document_id: s.image_sha256 for s in pool.samples}
    by_document = {r.document_id: r for r in ocr}
    if len(by_document) != len(ocr) or set(by_document) - documents.keys():
        raise ValueError("duplicate/out-of-pool OCR")
    if any(r.image_sha256 != documents[r.document_id] for r in ocr):
        raise ValueError("OCR image mismatch")
    predictions = {r.prediction.qid: r.prediction for r in batch.observations}
    result = {"P3-check": [], "P3-snap": []}
    for sample in sorted(pool.samples, key=lambda s: s.question.qid):
        qid = sample.question.qid
        value = VerifierInput(
            sample=sample,
            prediction=predictions.get(qid, AnswerPrediction(qid=qid, status="error")),
            ocr=by_document.get(sample.question.document_id),
        )
        for variant in result:
            result[variant].append(verify(value, profile.config, snap=variant == "P3-snap"))
    return result


def packed(decisions):
    return {k: [d.model_dump(mode="json") for d in v] for k, v in decisions.items()}


def write_bundle(output, pool, student, ocr, profile):
    if student.source != "student":
        raise ValueError("bundle requires student predictions")
    result = decisions(pool, student, ocr, profile)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("pool.json", pool),
        ("student.json", student),
        ("profile.json", profile),
        ("ocr.json", [r.model_dump(mode="json") for r in ocr]),
        ("decisions.json", packed(result)),
    ):
        write_model(output / name, value)
    write_model(
        output / "manifest.json",
        {
            "protocol": "verification_bundle_v1",
            "complete": True,
            "files": {name: sha256(output / name) for name in sorted(FILES)},
        },
    )
    return result


def load_bundle(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("protocol") != "verification_bundle_v1"
        or manifest.get("complete") is not True
        or set(manifest.get("files", {})) != FILES
    ):
        raise ValueError("invalid/incomplete verification bundle")
    if any(sha256(directory / n) != manifest["files"][n] for n in FILES):
        raise ValueError("verification bundle checksum mismatch")
    pool = read_model(directory / "pool.json", VerificationPool)
    batch = read_model(directory / "student.json", VerificationBatch)
    if batch.source != "student":
        raise ValueError("bundle requires student predictions")
    profile = read_model(directory / "profile.json", VerifierProfile)
    ocr = [
        OCRResult.model_validate(r)
        for r in json.loads((directory / "ocr.json").read_text(encoding="utf-8"))
    ]
    result = decisions(pool, batch, ocr, profile)
    if packed(result) != json.loads((directory / "decisions.json").read_text(encoding="utf-8")):
        raise ValueError("verification replay differs; create a new versioned run")
    return pool, batch, ocr, profile, result
