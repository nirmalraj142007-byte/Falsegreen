from __future__ import annotations

import pytest
from typer.testing import CliRunner

from falsegreen import __version__
from falsegreen.cli.main import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_runs_without_crashing() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert "falsegreen doctor" in result.stdout


@pytest.mark.parametrize(
    "command",
    ["db", "sandbox", "checkpoint", "data", "agent", "bench", "audit", "replay", "demo", "publish"],
)
def test_stub_commands_raise_not_implemented(command: str) -> None:
    result = runner.invoke(app, [command])
    assert result.exit_code != 0
    assert isinstance(result.exception, NotImplementedError)
