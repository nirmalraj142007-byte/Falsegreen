from __future__ import annotations

import sys

import pytest
from typer.testing import CliRunner

from falsegreen import __version__, errors
from falsegreen.cli import db as db_cli
from falsegreen.cli import main as cli_main
from falsegreen.cli.main import app
from falsegreen.config import get_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
    ["sandbox", "checkpoint", "data", "agent", "bench", "audit", "replay", "demo", "publish"],
)
def test_stub_commands_raise_not_implemented(command: str) -> None:
    result = runner.invoke(app, [command])
    assert result.exit_code != 0
    assert isinstance(result.exception, NotImplementedError)


def test_db_init_and_stats(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("FALSEGREEN_DB_PATH", str(db_path))

    init_result = runner.invoke(app, ["db", "init"])
    assert init_result.exit_code == 0
    assert db_path.exists()

    stats_result = runner.invoke(app, ["db", "stats"])
    assert stats_result.exit_code == 0
    assert "instance" in stats_result.stdout


def test_db_seed_and_stats_show_five_instances(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("FALSEGREEN_DB_PATH", str(db_path))

    assert runner.invoke(app, ["db", "init"]).exit_code == 0
    seed_result = runner.invoke(app, ["db", "seed", "--fixtures"])
    assert seed_result.exit_code == 0

    stats_result = runner.invoke(app, ["db", "stats"])
    assert stats_result.exit_code == 0


def test_db_seed_without_fixtures_flag_is_a_noop(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("FALSEGREEN_DB_PATH", str(db_path))
    assert runner.invoke(app, ["db", "init"]).exit_code == 0

    result = runner.invoke(app, ["db", "seed"])
    assert result.exit_code == 0
    assert "Nothing to seed" in result.stdout


def test_db_seed_fixtures_missing_raises_config_error_not_traceback(monkeypatch, tmp_path) -> None:
    """Outside a source checkout (e.g. an installed wheel) tests/fixtures/ does not exist.

    That must surface as a FalseGreenError with a remedy, never a raw FileNotFoundError.
    """
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("FALSEGREEN_DB_PATH", str(db_path))
    monkeypatch.setattr(db_cli, "FIXTURES_PATH", tmp_path / "nonexistent" / "instances_sample.json")
    assert runner.invoke(app, ["db", "init"]).exit_code == 0

    result = runner.invoke(app, ["db", "seed", "--fixtures"])

    assert result.exit_code != 0
    assert isinstance(result.exception, errors.ConfigError)
    assert "source checkout" in str(result.exception)


def test_db_vacuum(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("FALSEGREEN_DB_PATH", str(db_path))
    assert runner.invoke(app, ["db", "init"]).exit_code == 0

    result = runner.invoke(app, ["db", "vacuum"])
    assert result.exit_code == 0


def test_bare_invocation_prints_help_via_installed_entry_point(monkeypatch, capsys) -> None:
    """no_args_is_help must survive through run(), the real `falsegreen` console script."""
    monkeypatch.setattr(sys, "argv", ["falsegreen"])

    with pytest.raises(SystemExit) as exc_info:
        cli_main.run()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    for command in ("db", "doctor", "sandbox", "checkpoint", "data", "agent", "bench"):
        assert command in output


def test_main_handles_falsegreen_error_without_traceback(monkeypatch, capsys) -> None:
    def _raise_config_error() -> None:
        raise errors.ConfigError("boom")

    monkeypatch.setattr(cli_main, "app", _raise_config_error)

    with pytest.raises(SystemExit) as exc_info:
        cli_main.run()

    assert exc_info.value.code == errors.ConfigError.exit_code
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "Traceback" not in captured.err
