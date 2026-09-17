from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from falsegreen.config import get_settings
from falsegreen.errors import ConfigError
from falsegreen.store.db import connect, init_db
from falsegreen.store.models import Instance
from falsegreen.store.repositories import InstanceRepo

app = typer.Typer(name="db", no_args_is_help=True, help="Manage the results database.")

_TABLES = (
    "instance",
    "checkpoint",
    "run",
    "candidate",
    "execution",
    "verdict",
    "guardrail_event",
    "finding",
    "metric_snapshot",
    "prior_art",
)

FIXTURES_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "instances_sample.json"


@app.command()
def init() -> None:
    """Create the database file and apply all pending migrations."""
    settings = get_settings()
    init_db(settings.db_path)
    typer.echo(f"Initialized database at {settings.db_path}")


@app.command()
def stats() -> None:
    """Print row counts for every table."""
    settings = get_settings()
    conn = connect(settings.db_path)
    try:
        table = Table(title="falsegreen db stats")
        table.add_column("table")
        table.add_column("rows", justify="right")
        for name in _TABLES:
            count = conn.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
            table.add_row(name, str(count))
        Console().print(table)
    finally:
        conn.close()


@app.command()
def seed(
    fixtures: bool = typer.Option(
        False, "--fixtures", help="Load the bundled fixture instances."
    ),
) -> None:
    """Seed the database with fixture data."""
    if not fixtures:
        typer.echo("Nothing to seed. Pass --fixtures to load the fixture dataset.")
        return
    if not FIXTURES_PATH.exists():
        raise ConfigError(
            f"Fixture dataset not found at {FIXTURES_PATH}. `db seed --fixtures` is a "
            "dev-only convenience that reads tests/fixtures/ from a source checkout; it is "
            "not bundled in an installed wheel. Run this command from a `falsegreen` "
            "source checkout instead."
        )
    settings = get_settings()
    conn = connect(settings.db_path)
    try:
        raw = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        instances = [Instance.model_validate(row) for row in raw]
        InstanceRepo(conn).upsert_many(instances)
        conn.commit()
        typer.echo(f"Seeded {len(instances)} instances from {FIXTURES_PATH.name}")
    finally:
        conn.close()


@app.command()
def vacuum() -> None:
    """Reclaim disk space by vacuuming the database."""
    settings = get_settings()
    conn = connect(settings.db_path)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()
    typer.echo("Vacuumed database.")
