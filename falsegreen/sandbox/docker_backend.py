from __future__ import annotations

import asyncio
import shlex
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from falsegreen.errors import CheckpointBuildFailed, ForkFailed, ImageImportFailed
from falsegreen.sandbox.base import CheckpointHandle, ExecResult, ForkHandle

_STDOUT_TAIL_BYTES = 4096


async def _run_docker(*args: str) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout, stderr


def _tail(data: bytes) -> str:
    return data[-_STDOUT_TAIL_BYTES:].decode("utf-8", errors="replace")


def _parse_mem_to_mb(value: str) -> float | None:
    units = {"gib": 1024.0, "mib": 1.0, "kib": 1.0 / 1024.0, "b": 1.0 / (1024.0 * 1024.0)}
    lowered = value.lower()
    for suffix, factor in units.items():
        if lowered.endswith(suffix):
            number = value[: len(value) - len(suffix)].strip()
            try:
                return float(number) * factor
            except ValueError:
                return None
    return None


class DockerBackend:
    """Local Docker CLI backend. Never used to produce a published number.

    Mirrors Contree's filesystem-only snapshot semantics: `fork` is a `docker
    create` from a checkpoint image, so the same call sequence is correct
    against either backend.
    """

    name = "docker"

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex

    async def import_image(self, context_dir: Path, tag: str) -> str:
        code, _out, err = await _run_docker("build", "-t", tag, str(context_dir))
        if code != 0:
            raise ImageImportFailed(
                f"docker build failed for {context_dir} (tag {tag}): {_tail(err)}"
            )
        return tag

    async def build_checkpoint(
        self,
        image_ref: str,
        setup_cmds: list[str],
        verify_cmd: str,
        services_script: str | None,
    ) -> CheckpointHandle:
        container = f"falsegreen-build-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()
        try:
            code, _out, err = await _run_docker(
                "create", "--name", container, image_ref, "sleep", "infinity"
            )
            if code != 0:
                raise CheckpointBuildFailed(
                    f"docker create failed for {image_ref}: {_tail(err)}"
                )

            code, _out, err = await _run_docker("start", container)
            if code != 0:
                raise CheckpointBuildFailed(f"docker start failed for {container}: {_tail(err)}")

            for setup_cmd in setup_cmds:
                code, _out, err = await _run_docker("exec", container, "sh", "-c", setup_cmd)
                if code != 0:
                    raise CheckpointBuildFailed(
                        f"setup command {setup_cmd!r} failed in {container}: {_tail(err)}"
                    )

            code, out, err = await _run_docker("exec", container, "sh", "-c", verify_cmd)
            if code != 0:
                raise CheckpointBuildFailed(
                    f"verify command {verify_cmd!r} exited {code} in {container}: "
                    f"{_tail(out + err)}"
                )

            checkpoint_tag = f"falsegreen-checkpoint:{uuid.uuid4().hex[:12]}"
            code, _out, err = await _run_docker("commit", container, checkpoint_tag)
            if code != 0:
                raise CheckpointBuildFailed(f"docker commit failed for {container}: {_tail(err)}")
        finally:
            await _run_docker("rm", "-f", container)

        return CheckpointHandle(
            checkpoint_id=checkpoint_tag,
            image_ref=checkpoint_tag,
            backend=self.name,
            test_command=verify_cmd,
            services_script=services_script,
            build_seconds=time.monotonic() - start,
        )

    async def fork(self, checkpoint: CheckpointHandle) -> ForkHandle:
        fork_id = f"falsegreen-fork-{uuid.uuid4().hex[:12]}"
        code, _out, err = await _run_docker(
            "create",
            "--name",
            fork_id,
            "--label",
            f"falsegreen.run={self.run_id}",
            checkpoint.image_ref,
            "sleep",
            "infinity",
        )
        if code != 0:
            raise ForkFailed(
                f"docker create failed forking checkpoint {checkpoint.checkpoint_id}: {_tail(err)}"
            )

        code, _out, err = await _run_docker("start", fork_id)
        if code != 0:
            raise ForkFailed(f"docker start failed for fork {fork_id}: {_tail(err)}")

        return ForkHandle(
            fork_id=fork_id,
            checkpoint_id=checkpoint.checkpoint_id,
            backend=self.name,
            created_at=datetime.now(timezone.utc),
        )

    async def write_file(self, fork: ForkHandle, path: str, content: str) -> None:
        quoted = shlex.quote(path)
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            "-i",
            fork.fork_id,
            "sh",
            "-c",
            f"mkdir -p \"$(dirname {quoted})\" && cat > {quoted}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await proc.communicate(content.encode("utf-8"))
        if proc.returncode != 0:
            raise ForkFailed(f"writing {path} into fork {fork.fork_id} failed: {_tail(err)}")

    async def exec(self, fork: ForkHandle, cmd: str, timeout_s: int) -> ExecResult:
        start = time.monotonic()
        try:
            code, out, err = await asyncio.wait_for(
                _run_docker("exec", fork.fork_id, "sh", "-c", cmd), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                await _run_docker("kill", fork.fork_id)
            except OSError:
                pass
            return ExecResult(
                exit_code=124,
                stdout_tail="",
                duration_ms=duration_ms,
                was_fork=True,
                timed_out=True,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        cpu_ms, mem_peak_mb = await self._stats(fork.fork_id)
        return ExecResult(
            exit_code=code,
            stdout_tail=_tail(out + err),
            duration_ms=duration_ms,
            cpu_ms=cpu_ms,
            mem_peak_mb=mem_peak_mb,
            was_fork=True,
            timed_out=False,
        )

    async def _stats(self, container: str) -> tuple[int | None, float | None]:
        code, out, _err = await _run_docker(
            "stats", "--no-stream", "--format", "{{.MemUsage}}", container
        )
        if code != 0:
            return None, None
        raw = out.decode("utf-8", errors="ignore").strip()
        if not raw:
            return None, None
        mem_current = raw.split("/")[0].strip()
        # docker stats reports CPU as an instantaneous percentage over the sampling
        # window, not a cumulative duration, so there is no unit-correct way to
        # derive cpu_ms from it here; leave it None rather than fabricate a number.
        return None, _parse_mem_to_mb(mem_current)

    async def destroy(self, fork: ForkHandle) -> None:
        await _run_docker("rm", "-f", fork.fork_id)

    async def gc(self, *, all_runs: bool = False, run_id: str | None = None) -> int:
        if run_id is not None:
            label_filter = f"label=falsegreen.run={run_id}"
        elif all_runs:
            label_filter = "label=falsegreen.run"
        else:
            label_filter = f"label=falsegreen.run={self.run_id}"
        code, out, _err = await _run_docker("ps", "-aq", "--filter", label_filter)
        if code != 0:
            return 0
        ids = [line for line in out.decode("utf-8").splitlines() if line.strip()]
        if not ids:
            return 0
        await _run_docker("rm", "-f", *ids)
        return len(ids)
