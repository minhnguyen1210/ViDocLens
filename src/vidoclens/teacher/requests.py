"""Deterministic payloads and complete cache identities; no gold loader imports."""

import base64
import hashlib
import json
from pathlib import Path

from vidoclens.contracts.teacher import TeacherOutput, TeacherQuery, TeacherRequest

WIRE_POLICY = {"store": False, "service_tier": "default", "truncation": "disabled"}


def canonical(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def chunks(questions, *, max_questions=8, max_utf8_bytes=12000):
    """Keep ordered input, never silently drop an oversized question."""
    if max_questions < 1 or max_utf8_bytes < 1:
        raise ValueError("chunk limits must be positive")
    rows = tuple(TeacherQuery.model_validate(q.model_dump()) for q in questions)
    if not rows or len({q.qid for q in rows}) != len(rows):
        raise ValueError("questions must be nonempty with unique IDs")
    current = []
    for row in rows:
        candidate = [*current, row]
        size = len(canonical([q.model_dump() for q in candidate]).encode("utf-8"))
        if current and (len(candidate) > max_questions or size > max_utf8_bytes):
            yield tuple(current)
            current = []
        if len(canonical([row.model_dump()]).encode("utf-8")) > max_utf8_bytes:
            raise ValueError("single question exceeds byte limit")
        current.append(row)
    if current:
        yield tuple(current)


def identity(request: TeacherRequest, prompt: str) -> dict:
    request = TeacherRequest.model_validate(request.model_dump())
    if not prompt.strip():
        raise ValueError("empty prompt")
    data = request.model_dump(mode="json", exclude={"image_path"})
    # Partition/purpose also isolate evaluation and training caches.
    return {
        "request": data,
        "prompt": prompt,
        "output_schema": TeacherOutput.model_json_schema(),
        "wire_policy": WIRE_POLICY,
        "renderer_version": "responses_receipt_v1",
    }


def request_key(request: TeacherRequest, prompt: str) -> str:
    return digest(identity(request, prompt))


def build_body(request: TeacherRequest, prompt: str, root: Path) -> dict:
    identity(request, prompt)  # Revalidate mutable nested objects at the trust boundary.
    question_data = {"questions": [q.model_dump() for q in request.questions]}
    if request.ocr_text is not None:
        question_data["ocr_text"] = request.ocr_text
    content = [{"type": "input_text", "text": canonical(question_data)}]
    if request.profile.modality != "ocr_text":
        path = (root / request.image_path).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("image must stay in project workspace")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != request.image_sha256:
            raise ValueError("image bytes changed")
        if payload.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        else:
            raise ValueError("only verified JPEG/PNG bytes are supported")
        if len(payload) > 20_000_000:
            raise ValueError("image exceeds project request byte limit")
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:{mime};base64," + base64.b64encode(payload).decode("ascii"),
                "detail": request.profile.image_detail,
            }
        )
    return {
        "model": request.profile.model_snapshot,
        **WIRE_POLICY,
        "reasoning": {"effort": request.profile.reasoning_effort},
        "max_output_tokens": request.profile.max_output_tokens,
        "instructions": prompt,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "receipt_answers_v2",
                "strict": True,
                "schema": TeacherOutput.model_json_schema(),
            }
        },
    }
