"""Responses REST adapter. No SDK retries, tools, redirects or network calls on import."""

import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from pydantic import ValidationError

from vidoclens.contracts.teacher import TeacherOutput, TeacherRequest, TeacherResult, TeacherUsage


def parse_response(raw: dict, request: TeacherRequest, key: str) -> TeacherResult:
    common = {"request_key": key}
    if not isinstance(raw, dict):
        return TeacherResult(**common, status="schema_error", error_code="response_not_object")
    common["provider_response_id"] = raw.get("id") if isinstance(raw.get("id"), str) else None
    common["resolved_model"] = raw.get("model") if isinstance(raw.get("model"), str) else None
    usage = raw.get("usage")
    try:
        if isinstance(usage, dict):
            common["usage"] = TeacherUsage(
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cached_input_tokens=(usage.get("input_tokens_details") or {}).get(
                    "cached_tokens", 0
                ),
                total_tokens=usage["total_tokens"],
            )
    except (KeyError, TypeError, AttributeError, ValidationError):
        common["usage"] = None

    def failure(status, code):
        return TeacherResult(**common, status=status, error_code=code)

    if raw.get("status") == "incomplete":
        return failure("incomplete", "provider_incomplete")
    if raw.get("status") != "completed":
        return failure("provider_error", "response_not_completed")
    if common["resolved_model"] != request.profile.model_snapshot:
        return failure("model_mismatch", "snapshot_not_resolved_as_requested")
    if raw.get("service_tier", "default") != "default":
        return failure("provider_error", "unpriced_service_tier")
    try:
        outputs = raw["output"]
        if not isinstance(outputs, list):
            raise TypeError
        texts = []
        for item in outputs:
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or item.get("role") != "assistant":
                return failure("schema_error", "unexpected_output_item")
            if item.get("status") != "completed":
                return failure("incomplete", "message_not_completed")
            for content in item["content"]:
                if content.get("type") == "refusal":
                    return failure("refused", "provider_refusal")
                if content.get("type") != "output_text":
                    return failure("schema_error", "unexpected_content_type")
                texts.append(content["text"])
        if len(texts) != 1:
            return failure("schema_error", "expected_single_json_output")
        parsed = TeacherOutput.model_validate_json(texts[0])
    except (KeyError, TypeError, AttributeError, ValidationError):
        return failure("schema_error", "invalid_structured_output")
    qids = [x.qid for x in parsed.labels]
    if len(set(qids)) != len(qids) or set(qids) != {q.qid for q in request.questions}:
        return failure("qid_error", "missing_duplicate_or_unknown_qid")
    if common.get("usage") is None:
        return failure("usage_error", "missing_or_invalid_usage")
    labels = {label.qid: label for label in parsed.labels}
    return TeacherResult(
        **common, status="ok", labels=tuple(labels[q.qid] for q in request.questions)
    )


def retry_delay(header: str | None, retry: int, jitter: float, *, now=None) -> float:
    delay = min(30.0, 2.0**retry) + max(0, min(1, jitter))
    if header:
        try:
            required = float(header)
        except ValueError:
            try:
                date = parsedate_to_datetime(header)
                required = (date - (now or datetime.now(UTC))).total_seconds()
            except (ValueError, TypeError, OverflowError):
                required = 0
        delay = max(delay, required)
    return delay


class OpenAIProvider:
    def __init__(self, api_key: str, *, transport=None, timeout=60.0):
        import httpx

        if not api_key.strip():
            raise ValueError("API key not configured")
        self.client = httpx.Client(
            base_url="https://api.openai.com/v1/",
            headers={"Authorization": "Bearer " + api_key},
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    def close(self):
        self.client.close()

    def response(self, body):
        return self.client.post("responses", json=body)

    def upload_batch(self, payload: bytes):
        return self.client.post(
            "files",
            data={"purpose": "batch"},
            files={"file": ("requests.jsonl", payload, "application/jsonl")},
        )

    def create_batch(self, file_id: str):
        self._id(file_id, "file-")
        return self.client.post(
            "batches",
            json={
                "input_file_id": file_id,
                "endpoint": "/v1/responses",
                "completion_window": "24h",
            },
        )

    @staticmethod
    def _id(value, prefix):
        if not value.startswith(prefix) or not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("unsafe provider identifier")

    def get_batch(self, batch_id):
        self._id(batch_id, "batch_")
        return self.client.get("batches/" + batch_id)

    def get_file(self, file_id):
        self._id(file_id, "file-")
        return self.client.get("files/" + file_id + "/content")

    def delete_file(self, file_id):
        self._id(file_id, "file-")
        return self.client.delete("files/" + file_id)


def response_json(response):
    if response.status_code in {401, 403}:
        # Authentication error messages can echo credential fragments. Preserve the
        # HTTP outcome, never store the provider's free-form authentication message.
        return {"http_status": response.status_code, "authentication_message_omitted": True}
    try:
        obj = response.json()
        return obj if isinstance(obj, dict) else {"invalid_response": True}
    except (ValueError, json.JSONDecodeError):
        # Never log arbitrary HTML, request headers or transport exception bodies.
        return {"invalid_response": True, "http_status": response.status_code}
