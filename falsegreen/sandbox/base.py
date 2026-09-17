from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, field_validator

_STDOUT_TAIL_BYTES = 4096


class CheckpointHandle(BaseModel):
    checkpoint_id: str
    image_ref: str
    backend: str
    test_command: str
    services_script: str | None = None
    build_seconds: float


class ForkHandle(BaseModel):
    fork_id: str
    checkpoint_id: str
    backend: str
    created_at: datetime


class ExecResult(BaseModel):
    exit_code: int
    stdout_tail: str
    duration_ms: int
    cpu_ms: int | None = None
    mem_peak_mb: float | None = None
    io_bytes: int | None = None
    cost_cents: float | None = None
    provider_request_id: str | None = None
    was_fork: bool
    timed_out: bool = False

    @field_validator("stdout_tail")
    @classmethod
    def _truncate_tail(cls, value: str) -> str:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= _STDOUT_TAIL_BYTES:
            return value
        return encoded[-_STDOUT_TAIL_BYTES:].decode("utf-8", errors="ignore")


class SandboxBackend(Protocol):
    name: Literal["contree", "docker"]

    async def import_image(self, context_dir: Path, tag: str) -> str: ...

    async def build_checkpoint(
        self,
        image_ref: str,
        setup_cmds: list[str],
        verify_cmd: str,
        services_script: str | None,
    ) -> CheckpointHandle: ...

    async def fork(self, checkpoint: CheckpointHandle) -> ForkHandle: ...

    async def write_file(self, fork: ForkHandle, path: str, content: str) -> None: ...

    async def exec(self, fork: ForkHandle, cmd: str, timeout_s: int) -> ExecResult: ...

    async def destroy(self, fork: ForkHandle) -> None: ...

    async def gc(self, *, all_runs: bool = False, run_id: str | None = None) -> int: ...
