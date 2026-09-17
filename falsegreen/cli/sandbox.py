from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table

from falsegreen.errors import ConfigError
from falsegreen.sandbox.factory import get_backend

app = typer.Typer(name="sandbox", no_args_is_help=True, help="Manage sandbox backends and checkpoints.")

TINYREPO_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tinyrepo"


async def _smoke(backend_name: str) -> None:
    if not TINYREPO_PATH.exists():
        raise ConfigError(
            f"Fixture repo not found at {TINYREPO_PATH}. `sandbox smoke` is a dev-only "
            "convenience that reads tests/fixtures/ from a source checkout; it is not "
            "bundled in an installed wheel. Run this command from a `falsegreen` source "
            "checkout instead."
        )

    backend = get_backend(backend_name)
    tag = f"falsegreen-tinyrepo:{uuid4().hex[:8]}"

    image_ref = await backend.import_image(TINYREPO_PATH, tag)
    checkpoint = await backend.build_checkpoint(
        image_ref, setup_cmds=[], verify_cmd="python -m pytest -q", services_script=None,
    )
    fork = await backend.fork(checkpoint)
    try:
        await backend.write_file(
            fork, "tests/test_injected.py", "def test_ok():\n    assert True\n"
        )
        result = await backend.exec(fork, checkpoint.test_command, timeout_s=60)
    finally:
        await backend.destroy(fork)

    table = Table(title="falsegreen sandbox smoke")
    table.add_column("field")
    table.add_column("value")
    table.add_row("backend", backend.name)
    table.add_row("image ref", image_ref)
    table.add_row("fork id", fork.fork_id)
    table.add_row("exit code", str(result.exit_code))
    table.add_row("duration_ms", str(result.duration_ms))
    table.add_row("was_fork", str(result.was_fork))
    Console().print(table)


@app.command()
def smoke(
    backend: str = typer.Option(
        ..., "--backend", help="Sandbox backend to exercise: docker or contree."
    ),
) -> None:
    """Import the tinyrepo fixture, build a checkpoint, fork it, and run its tests."""
    asyncio.run(_smoke(backend))


@app.command()
def gc(
    backend: str = typer.Option(
        # TODO(phase-3): default to Settings.backend once ContreeBackend exists
        "docker", "--backend", help="Sandbox backend to garbage-collect orphaned forks on."
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Reclaim orphaned containers from every run, unless given."
    ),
) -> None:
    """Remove orphaned sandbox forks and report how many were removed."""
    backend_impl = get_backend(backend)
    if run_id is not None:
        count = asyncio.run(backend_impl.gc(run_id=run_id))
    else:
        count = asyncio.run(backend_impl.gc(all_runs=True))
    typer.echo(f"Removed {count} orphaned sandbox container(s).")
