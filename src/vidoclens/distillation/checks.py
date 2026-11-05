"""Capture actual local checks and their code/config/schema hashes for the G4 audit."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vidoclens.common.pilot import sha256
from vidoclens.filtering.io import write_model


def source_hashes(root):
    result = {}
    for folder in ("src", "tests", "scripts", "configs", "schemas", "infra/requirements"):
        for p in (root / folder).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}:
                result[p.relative_to(root).as_posix()] = sha256(p)
    result["pyproject.toml"] = sha256(root / "pyproject.toml")
    return result


def run(root, output):
    root = root.resolve()
    output = root / output
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes(root)
    commands = {
        "pytest": ["-m", "pytest", "-q"],
        "ruff": ["-m", "ruff", "check", "."],
        "format": ["-m", "ruff", "format", "--check", "."],
        "doctor": ["-m", "vidoclens", "doctor"],
        "schemas": ["scripts/export_schemas.py", "--check"],
        "repository": ["scripts/check_repo.py"],
    }
    results = {}
    for name, args in commands.items():
        path = output / f"{name}.log"
        with path.open("x", encoding="utf-8") as log:
            code = subprocess.run(
                [sys.executable, *args], cwd=root, stdout=log, stderr=subprocess.STDOUT, check=False
            ).returncode
        results[name] = {
            "command": ["python", *args],
            "exit_code": code,
            "log_sha256": sha256(path),
        }
        print(json.dumps({"check": name, "exit_code": code}), flush=True)
    if before != source_hashes(root):
        raise ValueError("code changed during checks; preserve logs and rerun in a new directory")
    report = {
        "status": "pass" if all(r["exit_code"] == 0 for r in results.values()) else "fail",
        "checks": results,
        "source_hashes": before,
        "python": sys.version,
        "gpu_execution_proof": False,
        "github_ci_claimed": False,
    }
    write_model(output / "checks.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    result = run(**vars(p.parse_args()))
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
