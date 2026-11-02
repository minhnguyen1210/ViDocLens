import json

from typer.testing import CliRunner

from vidoclens.cli import app


def test_documented_doctor_subcommand_runs_offline():
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["inference_ready"] is False
