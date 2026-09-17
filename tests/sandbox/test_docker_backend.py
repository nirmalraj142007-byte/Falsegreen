from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from falsegreen.sandbox.base import ForkHandle
from falsegreen.sandbox.docker_backend import DockerBackend

TINYREPO_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tinyrepo"


class _FakeProcess:
    def __init__(self, hang: bool) -> None:
        self._hang = hang
        self.returncode = 0

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        if self._hang:
            await asyncio.sleep(10)
        return b"", b""


async def test_exec_timeout_returns_124_and_timed_out(monkeypatch) -> None:
    calls = {"n": 0}

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls["n"] += 1
        # The first call is the hanging `docker exec`; the follow-up `docker kill`
        # must return promptly so the test itself does not hang.
        return _FakeProcess(hang=calls["n"] == 1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    backend = DockerBackend()
    fork = ForkHandle(
        fork_id="fake-container",
        checkpoint_id="fake-checkpoint",
        backend="docker",
        created_at=datetime.now(timezone.utc),
    )

    result = await backend.exec(fork, "sleep 100", timeout_s=0.05)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.was_fork is True
    assert calls["n"] == 2


class _FakeGcProcess:
    def __init__(self, stdout: bytes) -> None:
        self._stdout = stdout
        self.returncode = 0

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
        return self._stdout, b""


async def test_gc_default_scopes_to_own_run_id(monkeypatch) -> None:
    backend = DockerBackend(run_id="run-a")
    calls: list[tuple] = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        if args[1:3] == ("ps", "-aq"):
            label_filter = args[4]
            if label_filter == "label=falsegreen.run=run-a":
                return _FakeGcProcess(b"container-run-a\n")
            return _FakeGcProcess(b"")
        return _FakeGcProcess(b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    removed = await backend.gc()

    assert removed == 1
    rm_calls = [c for c in calls if c[1] == "rm"]
    assert len(rm_calls) == 1
    assert "container-run-a" in rm_calls[0]


async def test_gc_all_runs_removes_containers_from_every_run(monkeypatch) -> None:
    backend = DockerBackend(run_id="run-a")
    calls: list[tuple] = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        if args[1:3] == ("ps", "-aq"):
            label_filter = args[4]
            if label_filter == "label=falsegreen.run":
                return _FakeGcProcess(b"container-run-a\ncontainer-run-b\n")
            return _FakeGcProcess(b"")
        return _FakeGcProcess(b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    removed = await backend.gc(all_runs=True)

    assert removed == 2
    rm_calls = [c for c in calls if c[1] == "rm"]
    assert len(rm_calls) == 1
    assert "container-run-a" in rm_calls[0]
    assert "container-run-b" in rm_calls[0]


async def test_gc_explicit_run_id_overrides_own_run_id(monkeypatch) -> None:
    backend = DockerBackend(run_id="run-a")
    calls: list[tuple] = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        if args[1:3] == ("ps", "-aq"):
            label_filter = args[4]
            if label_filter == "label=falsegreen.run=run-b":
                return _FakeGcProcess(b"container-run-b\n")
            return _FakeGcProcess(b"")
        return _FakeGcProcess(b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    removed = await backend.gc(run_id="run-b")

    assert removed == 1
    rm_calls = [c for c in calls if c[1] == "rm"]
    assert len(rm_calls) == 1
    assert "container-run-b" in rm_calls[0]


@pytest.mark.requires_docker
async def test_full_smoke_cycle_against_tinyrepo_fixture() -> None:
    backend = DockerBackend()
    tag = f"falsegreen-test-tinyrepo:{uuid.uuid4().hex[:8]}"

    image_ref = await backend.import_image(TINYREPO_PATH, tag)
    checkpoint = await backend.build_checkpoint(
        image_ref, setup_cmds=[], verify_cmd="python -m pytest -q", services_script=None,
    )
    fork = await backend.fork(checkpoint)
    try:
        result = await backend.exec(fork, checkpoint.test_command, timeout_s=60)
        assert result.exit_code == 0
        assert result.was_fork is True
    finally:
        await backend.destroy(fork)
        removed = await backend.gc()
        assert removed >= 0
