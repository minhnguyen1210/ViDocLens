import subprocess

import pytest

from scripts.check_repo import MAX_BYTES, candidates, file_problem
from scripts.export_schemas import export


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.local",
        "sub/.ENV.production",
        "data/raw/receipt.jpg",
        "artifacts/models/README.md",
        "artifacts/run/result.json",
        "cache/model.json",
        ".venv/pyvenv.cfg",
        "weights/student.safetensors",
        "run.sqlite-wal",
    ],
)
def test_payload_rejected_even_if_force_staged(name):
    assert file_problem(name, 10)


@pytest.mark.parametrize(
    "name",
    [
        ".env.example",
        "src/vidoclens/data/images.py",
        "data/raw/README.md",
        "artifacts/.gitkeep",
        "docs/DATA_CARD.md",
    ],
)
def test_source_and_scaffold_allowed(name):
    assert file_problem(name, 10) is None


def test_size_boundary():
    assert file_problem("notes.txt", MAX_BYTES) is None
    assert file_problem("notes.txt", MAX_BYTES + 1)


def test_staged_check_uses_index_not_changed_worktree(tmp_path):
    # Isolated temporary repository; never stage files in the user's repository.
    def run(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    run("init")
    file = tmp_path / "notes.txt"
    file.write_bytes(b"staged")
    run("add", "notes.txt")
    file.write_bytes(b"different unstaged contents")
    assert candidates(tmp_path, staged=True) == [("notes.txt", 6)]
    assert file.read_bytes() == b"different unstaged contents"


def test_schema_check_detects_missing_changed_and_stale_without_writes(tmp_path):
    root = tmp_path / "schemas"
    assert export(root, check=True)
    assert not root.exists()
    assert export(root) == []
    assert export(root, check=True) == []
    (root / "document.schema.json").write_text("{}", encoding="utf-8")
    (root / "stale.schema.json").write_text("{}", encoding="utf-8")
    (root / "ai_review_task.schema.json").unlink()
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    assert set(export(root, check=True)) == {
        "document.schema.json",
        "stale.schema.json",
        "ai_review_task.schema.json",
    }
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
