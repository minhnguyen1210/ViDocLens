"""F0/F1 offline decisions. No training gold, teacher calls, or model imports."""

from collections import Counter
from pathlib import Path

from vidoclens.contracts import silver as silver_contracts
from vidoclens.contracts.models import OCRResult
from vidoclens.contracts.silver import (
    FilterConfig,
    FilterDecision,
    FilterRun,
    SilverBatch,
    SilverPool,
)
from vidoclens.filtering import matching
from vidoclens.filtering.io import digest, revalidate


def implementation_hash() -> str:
    paths = [Path(__file__), Path(matching.__file__), Path(silver_contracts.__file__)]
    return digest({p.name: p.read_text(encoding="utf-8") for p in paths})


def validate_batch(pool: SilverPool, batch: SilverBatch):
    pool, batch = revalidate(pool), revalidate(batch)
    if batch.pool_sha256 != digest(pool):
        raise ValueError("teacher batch belongs to a different pool")
    samples = {s.question.qid: s for s in pool.samples}
    if set(r.qid for r in batch.labels) - samples.keys():
        raise ValueError("teacher returned unknown/out-of-scope qids")
    return pool, batch


def filter_batch(
    pool: SilverPool, batch: SilverBatch, ocr_results: list[OCRResult], config: FilterConfig
) -> FilterRun:
    pool, batch = validate_batch(pool, batch)
    config = revalidate(config)
    if config.status == "frozen_dev_select" and (
        config.freeze_access_plan_sha256 != pool.access_plan_sha256
        or config.freeze_fixture_only
        and not batch.fixture_only
    ):
        raise ValueError("filter freeze belongs to another split or synthetic evidence")
    if pool.partition == "audit_holdout" and config.status != "frozen_dev_select":
        raise PermissionError("freeze rules on dev_select before audit_holdout")
    ocr_results = [revalidate(r) for r in ocr_results]
    ocr = {r.document_id: r for r in ocr_results}
    if len(ocr) != len(ocr_results):
        raise ValueError("duplicate OCR documents")
    documents = {s.question.document_id: s.image_sha256 for s in pool.samples}
    if set(ocr) - documents.keys():
        raise ValueError("OCR contains documents outside this pool")
    for doc, result in ocr.items():
        if result.image_sha256 != documents[doc]:
            raise ValueError("OCR image hash mismatch")
    labels = {r.qid: r for r in batch.labels}
    indexes = {}
    decisions = []
    for sample in sorted(pool.samples, key=lambda s: s.question.qid):
        q = sample.question
        label = labels.get(q.qid)
        raw = label.answer_raw if label and label.status == "answered" else None
        base = dict(
            qid=q.qid,
            sample_sha256=digest(sample),
            label_sha256=digest(label) if label else None,
            answer_raw=raw,
            answer_normalized=matching.normalize(raw) if raw else None,
            answer_type=matching.answer_type(raw) if raw else "unknown",
            question_type=matching.question_type(q.question_raw),
            f0_keep=raw is not None,
        )
        if raw is None:
            decisions.append(
                FilterDecision(
                    **base, f1_keep=False, reason=label.status if label else "missing_label"
                )
            )
            continue
        try:
            raw_parts = matching.split_parts(raw, batch.part_protocol)
        except ValueError:
            base["f0_keep"] = False
            decisions.append(FilterDecision(**base, f1_keep=False, reason="invalid_answer_parts"))
            continue
        result = ocr.get(q.document_id)
        if result is None or result.status != "ok" or not result.spans:
            reason = "ocr_missing" if result is None else f"ocr_{result.status}"
            if result is not None and result.status == "ok":
                reason = "ocr_empty"
            decisions.append(FilterDecision(**base, f1_keep=False, reason=reason))
            continue
        if q.document_id not in indexes:
            try:
                indexes[q.document_id] = matching.candidates(result, config)
            except ValueError as exc:
                if str(exc) != "ocr_token_limit":
                    raise
                indexes[q.document_id] = None
        choices = indexes[q.document_id]
        if choices is None:
            decisions.append(FilterDecision(**base, f1_keep=False, reason="ocr_token_limit"))
            continue
        parts = tuple(matching.match_part(p, choices, config) for p in raw_parts)
        keep = all(p.support != "none" for p in parts)
        reason = (
            "all_parts_supported" if keep else next(p.reason for p in parts if p.support == "none")
        )
        used = set()
        for p in parts:
            if p.support == "none":
                continue
            tokens = set(range(p.token_start, p.token_end))
            if used & tokens:
                keep, reason = False, "overlapping_part_evidence"
            used |= tokens
        decisions.append(FilterDecision(**base, f1_keep=keep, reason=reason, parts=parts))
    return FilterRun(
        pool_sha256=digest(pool),
        batch_sha256=digest(batch),
        config=config,
        ocr_sha256=digest(
            [r.model_dump(mode="json") for r in sorted(ocr_results, key=lambda r: r.document_id)]
        ),
        implementation_sha256=implementation_hash(),
        decisions=tuple(decisions),
    )


def validate_run(pool, batch, run):
    """Recheck joins and raw targets before export or privileged gold evaluation."""
    pool, batch = validate_batch(pool, batch)
    run = revalidate(run)
    if run.pool_sha256 != digest(pool) or run.batch_sha256 != digest(batch):
        raise ValueError("filter run input identity mismatch")
    samples = {s.question.qid: s for s in pool.samples}
    labels = {r.qid: r for r in batch.labels}
    if set(d.qid for d in run.decisions) != samples.keys():
        raise ValueError("filter decisions must cover every requested qid")
    for d in run.decisions:
        label = labels.get(d.qid)
        raw = label.answer_raw if label and label.status == "answered" else None
        eligible = raw is not None
        try:
            raw_parts = matching.split_parts(raw, batch.part_protocol) if raw else ()
        except ValueError:
            eligible, raw_parts = False, ()
        if (
            d.sample_sha256 != digest(samples[d.qid])
            or d.label_sha256 != (digest(label) if label else None)
            or d.answer_raw != raw
            or d.answer_normalized != (matching.normalize(raw) if raw else None)
            or d.answer_type != (matching.answer_type(raw) if raw else "unknown")
            or d.question_type != matching.question_type(samples[d.qid].question.question_raw)
            or d.f0_keep != eligible
        ):
            raise ValueError("filter decision target/identity changed")
        if d.parts and tuple(p.text_raw for p in d.parts) != raw_parts:
            raise ValueError("filter changed answer parts")
    return pool, batch, run


def summarize(run: FilterRun) -> dict:
    run = revalidate(run)
    eligible = sum(d.f0_keep for d in run.decisions)
    kept = sum(d.f1_keep for d in run.decisions)
    return {
        "requested": len(run.decisions),
        "f0_eligible": eligible,
        "f1_kept": kept,
        "f1_retention": kept / eligible if eligible else None,
        "reasons": dict(sorted(Counter(d.reason for d in run.decisions).items())),
        "quality_measured": False,
        "semantic_correctness_verified": False,
    }
