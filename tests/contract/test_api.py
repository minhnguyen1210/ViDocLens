"""Safety and truthful readiness contract for the foundation HTTP surface."""

import pytest

from vidoclens.serving.api import MAX_UPLOAD_BYTES


def test_live_does_not_imply_ready(client):
    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["reason"] == "model_not_configured"


@pytest.mark.parametrize("endpoint", ["/v1/vqa", "/v1/extract"])
def test_valid_input_never_returns_fake_prediction(client, png_bytes, endpoint):
    response = client.post(
        endpoint,
        data={"question": "Tổng tiền là bao nhiêu?"},
        files={"image": ("receipt.png", png_bytes, "image/png")},
    )
    assert response.status_code == 501
    assert "not_implemented" in response.json()["detail"]["code"]
    assert "answer" not in response.json()


def test_content_type_cannot_hide_nonimage(client):
    response = client.post(
        "/v1/vqa",
        data={"question": "Tổng tiền?"},
        files={"image": ("receipt.png", b"not an image", "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_image"


def test_content_type_matches_actual_bytes(client, png_bytes):
    response = client.post(
        "/v1/extract",
        files={"image": ("receipt.jpg", png_bytes, "image/jpeg")},
    )
    assert response.status_code == 415


def test_oversize_file_rejected(client):
    response = client.post(
        "/v1/extract",
        files={"image": ("receipt.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")},
    )
    assert response.status_code == 413


@pytest.mark.parametrize("mode", ["openai", "cascade"])
def test_external_mode_requires_request_consent(client, png_bytes, mode):
    response = client.post(
        "/v1/vqa",
        data={"question": "Tổng tiền?", "mode": mode},
        files={"image": ("receipt.png", png_bytes, "image/png")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "external_processing_not_allowed"


def test_request_consent_cannot_override_server_policy(client, png_bytes):
    response = client.post(
        "/v1/extract",
        data={"mode": "openai", "allow_external": "true"},
        files={"image": ("receipt.png", png_bytes, "image/png")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "external_processing_disabled"


def test_whitespace_question_rejected(client, png_bytes):
    response = client.post(
        "/v1/vqa",
        data={"question": "   "},
        files={"image": ("receipt.png", png_bytes, "image/png")},
    )
    assert response.status_code == 422


def test_arbitrary_url_is_not_an_image_input(client):
    response = client.post(
        "/v1/vqa", data={"question": "Tổng tiền?", "image_url": "http://localhost/private"}
    )
    assert response.status_code == 422
