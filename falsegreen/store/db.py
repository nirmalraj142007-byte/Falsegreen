from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from falsegreen.errors import ConfigError

_SCHEMA_MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migration_files() -> list[tuple[int, str, str]]:
    """Discover (version, filename, sql) triples from package data.

    Uses importlib.resources rather than a path relative to the current
    working directory, so this works the same from an installed wheel as
    from the source tree.
    """
    migrations_dir = resources.files("falsegreen.store.migrations")
    entries: list[tuple[int, str, str]] = []
    for entry in migrations_dir.iterdir():
        if entry.name.endswith(".sql"):
            version = int(entry.name.split("_", 1)[0])
            entries.append((version, entry.name, entry.read_text(encoding="utf-8")))
    entries.sort(key=lambda item: item[0])
    return entries


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute(_SCHEMA_MIGRATION_TABLE_SQL)
    row = conn.execute("SELECT MAX(version) AS version FROM schema_migration").fetchone()
    return row["version"] or 0


def init_db(path: Path) -> None:
    """Apply every unapplied migration, in order, inside its own transaction. Idempotent."""
    conn = connect(path)
    try:
        conn.execute(_SCHEMA_MIGRATION_TABLE_SQL)
        conn.commit()
        applied = current_version(conn)
        migrations = _migration_files()
        on_disk_max = migrations[-1][0] if migrations else 0

        if applied > on_disk_max:
            raise ConfigError(
                f"Database at {path} is at schema version {applied}, but this checkout only "
                f"ships migrations up to version {on_disk_max}. This means an older checkout is "
                "pointing at a newer database. Update falsegreen to a version whose migrations "
                "include the database's version, or point db_path at a fresh database file."
            )

        for version, _name, sql in migrations:
            if version <= applied:
                continue
            with conn:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migration (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
    finally:
        conn.close()
