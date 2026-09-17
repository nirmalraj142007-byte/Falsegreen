from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from falsegreen.errors import ConfigError
from falsegreen.store.db import connect, current_version, init_db


def test_init_db_creates_all_tables(db_path: Path) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'schema_migration'"
        ).fetchall()
        names = {row["name"] for row in rows}
    finally:
        conn.close()
    assert names == {
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
    }


def test_init_db_creates_nine_indexes(db_path: Path) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 9


def test_connect_enables_wal_and_foreign_keys(db_path: Path) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_init_db_twice_is_a_noop_and_preserves_data(db_path: Path) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO prior_art (key, label, condition_note, citation) VALUES (?, ?, ?, ?)",
            ("k1", "label", "note", "cite"),
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)

    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM prior_art WHERE key = 'k1'").fetchone()
        version = current_version(conn)
    finally:
        conn.close()
    assert row is not None
    assert version == 1


def test_init_db_works_from_unrelated_cwd(db_path: Path, tmp_path: Path, monkeypatch) -> None:
    other_dir = tmp_path / "somewhere_else"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    assert os.getcwd() != str(db_path.parent)

    init_db(db_path)

    conn = connect(db_path)
    try:
        version = current_version(conn)
    finally:
        conn.close()
    assert version == 1


def test_version_ahead_of_disk_migrations_raises_config_error(db_path: Path) -> None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO schema_migration (version, applied_at) VALUES (999, '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ConfigError):
        init_db(db_path)


def test_foreign_key_violation_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO candidate ("
            "candidate_id, run_id, ordinal, hypothesis, test_code, test_path, model, prompt_hash"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("c1", "nonexistent-run", 0, "h", "code", "path", "model", "hash"),
        )
