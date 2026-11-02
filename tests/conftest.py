"""Fixtures use synthetic images only; no licensed receipt or external calls."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from vidoclens.serving.api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VIDOCLENS_EXTERNAL_ENABLED", "false")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def png_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(stream, format="PNG")
    return stream.getvalue()
