from __future__ import annotations

import json
import logging

from falsegreen.logging import bind_run_id, setup_logging


def test_setup_logging_emits_json_with_required_keys(capsys) -> None:
    setup_logging("INFO")
    bind_run_id("test-run-123")
    logging.getLogger("falsegreen.test").info("something_happened", extra={"foo": "bar"})

    captured = capsys.readouterr()
    record = json.loads(captured.err.strip().splitlines()[-1])

    assert record["event"] == "something_happened"
    assert record["level"] == "INFO"
    assert record["run_id"] == "test-run-123"
    assert record["foo"] == "bar"
    assert "ts" in record


def test_bind_run_id_defaults_to_dash(capsys) -> None:
    setup_logging("INFO")
    bind_run_id("-")
    logging.getLogger("falsegreen.test").info("no_run_bound")

    captured = capsys.readouterr()
    record = json.loads(captured.err.strip().splitlines()[-1])
    assert record["run_id"] == "-"
