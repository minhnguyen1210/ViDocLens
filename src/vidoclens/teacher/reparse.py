"""Strict item-level validation of original JSON; no inference, repair or target rewriting."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from vidoclens.common.pilot import sha256
from vidoclens.contracts.local_teacher import LocalGeneration, LocalTeacherAnswer, LocalTeacherPlan
from vidoclens.contracts.silver import SilverBatch, SilverLabel
from vidoclens.contracts.silver_reparse import SilverReparseManifest
from vidoclens.filtering.io import digest, read_model, write_model
from vidoclens.teacher.local_labels import parse_generation, request_ids


def parse_items(request, generation):
    """Only field-invalid individual rows are isolated; ambiguous envelopes fail closed."""
    if generation.status != "completed":
        return parse_generation(request, generation)
    raw_hash = hashlib.sha256(generation.raw_text.encode("utf-8")).hexdigest()

    def failure(qid, reason):
        return SilverLabel(
            qid=qid, status="parse_error", reason=reason, raw_response_sha256=raw_hash
        )

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        envelope = json.loads(generation.raw_text, object_pairs_hook=unique_keys)
        if (
            not isinstance(envelope, dict)
            or set(envelope) - {"schema_version", "answers"}
            or envelope.get("schema_version", "1.0") != "1.0"
            or not isinstance(envelope.get("answers"), list)
        ):
            raise ValueError("invalid output envelope")
        aliases = request_ids(request)
        rows = {}
        for row in envelope["answers"]:
            if not isinstance(row, dict) or not isinstance(row.get("qid"), str):
                raise ValueError("unidentifiable output item")
            key = row["qid"]
            if key not in aliases or key in rows:
                raise ValueError("duplicate or unknown output qid")
            rows[key] = row
    except (ValueError, TypeError):
        return tuple(failure(q.qid, "invalid_output_envelope_or_qids") for q in request.questions)
    result = []
    for alias, canonical in aliases.items():
        if alias not in rows:
            result.append(failure(canonical, "missing_qid"))
            continue
        try:
            answer = LocalTeacherAnswer.model_validate(rows[alias])
        except ValidationError:
            result.append(failure(canonical, "invalid_answer_item"))
            continue
        result.append(
            SilverLabel(
                qid=canonical,
                status="answered" if answer.answerable else "unanswerable",
                answer_raw=answer.answer,
                evidence_text=answer.evidence_text,
                reason=answer.reason_code,
                raw_response_sha256=raw_hash,
            )
        )
    return tuple(result)


def derive(source_run):
    source_run = source_run.resolve()
    source = json.loads((source_run / "manifest.json").read_text(encoding="utf-8"))
    plan = read_model(source_run / "plan.json", LocalTeacherPlan)
    batch = read_model(source_run / "batch.json", SilverBatch)
    if (
        source.get("complete") is not True
        or source["batch_sha256"] != digest(batch)
        or source["binding"]["plan"] != digest(plan)
    ):
        raise ValueError("reparse requires a complete checksum-bound original generation")
    uri = (source_run / "attempts.sqlite").as_uri() + "?mode=ro"
    original, parsed = [], []
    with sqlite3.connect(uri, uri=True) as db:
        binding = json.loads(db.execute("SELECT value FROM binding WHERE id=1").fetchone()[0])
        if binding != source["binding"]:
            raise ValueError("raw cache binding differs from complete manifest")
        expected_keys = {digest([binding, r.model_dump(mode="json")]) for r in plan.requests}
        if {r[0] for r in db.execute("SELECT DISTINCT key FROM attempts")} != expected_keys:
            raise ValueError("raw cache coverage differs from source plan")
        evidence = {r["key"]: r for r in source["requests"]}
        for request in plan.requests:
            key = digest([binding, request.model_dump(mode="json")])
            rows = db.execute(
                "SELECT number,generation,checksum FROM attempts WHERE key=? ORDER BY number",
                (key,),
            ).fetchall()
            if len(rows) != evidence[key]["attempts"]:
                raise ValueError("raw attempt count differs from completed source")
            history = []
            for index, (number, raw, checksum) in enumerate(rows, 1):
                generation = LocalGeneration.model_validate_json(raw)
                if number != index or digest(generation) != checksum:
                    raise ValueError("raw generation checksum/order differs")
                history.append(generation)
            if [digest(g) for g in history] != evidence[key]["all_generation_sha256s"]:
                raise ValueError("raw generation history differs from completed source")
            original.extend(parse_generation(request, history[-1]))
            parsed.extend(parse_items(request, history[-1]))
    if tuple(original) != batch.labels:
        raise ValueError("original batch does not replay; cannot derive a corrected parser view")
    derived = batch.model_copy(
        update={"run_id": batch.run_id + ":strict-items-v1", "labels": tuple(parsed)}
    )
    derived = SilverBatch.model_validate(derived.model_dump())
    report = SilverReparseManifest(
        source_run=str(source_run),
        source_manifest_sha256=sha256(source_run / "manifest.json"),
        source_plan_sha256=digest(plan),
        source_batch_sha256=digest(batch),
        parsed_batch_sha256=digest(derived),
        parser_sha256=sha256(Path(__file__)),
        fixture_only=batch.fixture_only,
        source_status_counts=dict(Counter(label.status for label in batch.labels)),
        parsed_status_counts=dict(Counter(label.status for label in derived.labels)),
    )
    return derived, report


def verify(source_run, directory):
    batch, report = derive(source_run)
    stored = read_model(directory / "manifest.json", SilverReparseManifest)
    # The source directory can be reached via Windows or WSL; byte/hash identity is binding.
    if (
        stored.model_dump(exclude={"source_run"}) != report.model_dump(exclude={"source_run"})
        or read_model(directory / "batch.json", SilverBatch) != batch
    ):
        raise ValueError("strict-item view differs from immutable raw source")
    return batch, report


def run(source_run, output):
    batch, report = derive(source_run)
    output.mkdir(parents=True, exist_ok=False)
    write_model(output / "batch.json", batch)
    write_model(output / "manifest.json", report)
    print(
        json.dumps(
            {
                "new_model_calls": 0,
                "source_status": report.source_status_counts,
                "parsed_status": report.parsed_status_counts,
            }
        ),
        flush=True,
    )
    return batch, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    run(**vars(p.parse_args()))


if __name__ == "__main__":
    main()
