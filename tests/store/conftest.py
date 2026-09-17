from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from falsegreen.store.db import connect, init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "results.db"


@pytest.fixture
def conn(db_path: Path) -> sqlite3.Connection:
    init_db(db_path)
    connection = connect(db_path)
    yield connection
    connection.close()
