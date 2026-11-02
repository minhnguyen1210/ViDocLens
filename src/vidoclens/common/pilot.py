"""Validation and diagnostics shared by explicitly invoked local pilot runners."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from vidoclens.contracts.pilot import Phase0PilotManifest, PilotReceipt


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    """Never replace an earlier run's evidence."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def checked_image(root: Path, row: PilotReceipt) -> Path:
    root = root.resolve()
    path = (root / row.image_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("pilot image escapes repository root")
    if sha256(path) != row.image_sha256:
        raise ValueError("pilot image hash mismatch")
    return path


def load_pilot(root: Path, manifest: Path, image_inventory: Path) -> Phase0PilotManifest:
    data = Phase0PilotManifest.model_validate_json(manifest.read_text(encoding="utf-8"))
    inventory = json.loads(image_inventory.read_text(encoding="utf-8"))
    train = {r["image_sha256"] for r in inventory if r["source_split"] == "train"}
    heldout = {r["image_sha256"] for r in inventory if r["source_split"] != "train"}
    for row in data.pilot:
        if row.image_sha256 not in train or row.image_sha256 in heldout:
            raise ValueError("pilot must belong exclusively to official train")
        checked_image(root, row)
    return data


def environment() -> dict:
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used",
                "--format=csv",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        gpu_output, gpu_code = gpu.stdout.strip(), gpu.returncode
    except FileNotFoundError:
        gpu_output, gpu_code = "nvidia-smi unavailable", 127
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": dict(sorted(packages.items())),
        "gpu_inventory": gpu_output,
        "gpu_inventory_exit_code": gpu_code,
    }


def snapshot_sources(output: Path, runner: Path) -> None:
    """Keep the actual source with uncommitted local runs, not only a transient hash."""
    import vidoclens.contracts.pilot as pilot_contract

    sources = {
        "runner.py": runner,
        "common_pilot.py": Path(__file__),
        "pilot_contract.py": Path(pilot_contract.__file__),
    }
    for name, path in sources.items():
        with (output / name).open("xb") as stream:
            stream.write(path.read_bytes())


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
