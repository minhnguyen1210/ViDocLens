"""Offline project diagnostics. No model downloads or billable calls."""

import importlib.util
import json
import platform
import shutil
from pathlib import Path

import typer

from vidoclens import __version__

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """ViDocLens project tools."""


@app.command()
def doctor() -> None:
    """Report installation capabilities; this does not certify GPU readiness."""
    report = {
        "project": "ViDocLens",
        "version": __version__,
        "stage": "foundation",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "workspace": str(Path.cwd()),
        "optional_packages": {
            name: importlib.util.find_spec(name) is not None
            for name in ("fastapi", "gradio", "torch", "transformers", "paddleocr")
        },
        "docker_cli_found": shutil.which("docker") is not None,
        "nvidia_smi_found": shutil.which("nvidia-smi") is not None,
        "inference_ready": False,
        "reason": "model_not_configured",
    }
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
