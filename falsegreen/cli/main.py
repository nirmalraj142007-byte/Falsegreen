from __future__ import annotations

import typer

from falsegreen import __version__
from falsegreen.cli import db as db_cli
from falsegreen.cli import sandbox as sandbox_cli
from falsegreen.cli.doctor import run_doctor
from falsegreen.errors import FalseGreenError

app = typer.Typer(name="falsegreen", no_args_is_help=True)
app.add_typer(db_cli.app, name="db")
app.add_typer(sandbox_cli.app, name="sandbox")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"falsegreen {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the falsegreen version and exit.",
    ),
) -> None:
    """FalseGreen: finds bugs nobody has reported yet, and proves each one."""


@app.command()
def doctor() -> None:
    """Check the local environment for everything falsegreen needs to run."""
    raise typer.Exit(code=run_doctor())


def _not_implemented(name: str) -> None:
    raise NotImplementedError(f"`falsegreen {name}` is not implemented yet.")


@app.command()
def checkpoint() -> None:
    """Build and manage per-repo warm checkpoints."""
    _not_implemented("checkpoint")


@app.command()
def data() -> None:
    """Load and filter benchmark instance data."""
    _not_implemented("data")


@app.command()
def agent() -> None:
    """Run the suspicion/hypothesis/synthesis agent loop."""
    _not_implemented("agent")


@app.command()
def bench() -> None:
    """Run a full benchmark sweep."""
    _not_implemented("bench")


@app.command()
def audit() -> None:
    """Audit a single repository at HEAD."""
    _not_implemented("audit")


@app.command()
def replay() -> None:
    """Replay a prior run's findings from the results database."""
    _not_implemented("replay")


@app.command()
def demo() -> None:
    """Run the scripted demo flow."""
    _not_implemented("demo")


@app.command()
def publish() -> None:
    """Publish the results dashboard."""
    _not_implemented("publish")


def run() -> None:
    """Console-script entry point: the single top-level FalseGreenError handler.

    A FalseGreenError propagates untouched from every command down here; nothing
    prints a Python traceback for an expected, taxonomized failure.
    """
    try:
        app()
    except FalseGreenError as exc:
        typer.echo(f"ERROR [{exc.code}]: {exc}", err=True)
        if exc.remedy:
            typer.echo(f"Remedy: {exc.remedy}", err=True)
        raise SystemExit(exc.exit_code) from None


if __name__ == "__main__":
    run()
