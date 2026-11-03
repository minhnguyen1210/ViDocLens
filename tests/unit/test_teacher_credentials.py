"""Fake credentials only. Never load the user's .env in tests."""

import pytest

from vidoclens.teacher.credentials import load_api_key


@pytest.mark.parametrize(
    "line",
    [
        "OPENAI_API_KEY=synthetic-value",
        'OPENAI_API_KEY="synthetic-value" # comment',
        "export OPENAI_API_KEY='synthetic-value'",
        "\ufeffOPENAI_API_KEY=synthetic-value",
    ],
)
def test_explicit_file_only_reads_key(tmp_path, monkeypatch, line):
    monkeypatch.setenv("OPENAI_API_KEY", "old-value")
    monkeypatch.setenv("VIDOCLENS_EXTERNAL_ENABLED", "false")
    (tmp_path / ".env").write_text(line + "\nVIDOCLENS_EXTERNAL_ENABLED=true\n", encoding="utf-8")
    assert load_api_key(tmp_path, tmp_path / ".env") == "synthetic-value"
    assert load_api_key(tmp_path) == "old-value"
    import os

    assert os.environ["VIDOCLENS_EXTERNAL_ENABLED"] == "false"


@pytest.mark.parametrize(
    "line",
    [
        "OPENAI_API_KEY=",
        "OPENAI_API_KEY='synthetic-hidden",
        "OPENAI_API_KEY=synthetic hidden",
        "OPENAI_API_KEY=synthetic-hidden\nOPENAI_API_KEY=second",
    ],
)
def test_bad_file_errors_never_echo_value(tmp_path, line):
    (tmp_path / ".env").write_text(line, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        load_api_key(tmp_path, tmp_path / ".env")
    assert "synthetic" not in str(exc.value) and "second" not in str(exc.value)
