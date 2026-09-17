from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from falsegreen.config import get_settings

MIN_FREE_DISK_GB = 20.0


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    remedy: str


def _check_python_version() -> CheckResult:
    major, minor = sys.version_info[:2]
    ok = (major, minor) == (3, 11)
    detail = f"Running Python {sys.version.split()[0]}"
    remedy = "" if ok else "Install Python 3.11 and run falsegreen inside that interpreter."
    return CheckResult("python_version", ok, detail, remedy)


def _check_nebius_credential() -> CheckResult:
    settings = get_settings()
    ok = settings.nebius_api_key is not None
    detail = "FALSEGREEN_NEBIUS_API_KEY is set" if ok else "FALSEGREEN_NEBIUS_API_KEY is not set"
    remedy = "" if ok else "Set the FALSEGREEN_NEBIUS_API_KEY environment variable."
    return CheckResult("nebius_credential", ok, detail, remedy)


def _check_contree_credential() -> CheckResult:
    settings = get_settings()
    ok = settings.contree_token is not None
    detail = "FALSEGREEN_CONTREE_TOKEN is set" if ok else "FALSEGREEN_CONTREE_TOKEN is not set"
    remedy = "" if ok else "Set the FALSEGREEN_CONTREE_TOKEN environment variable."
    return CheckResult("contree_credential", ok, detail, remedy)


def _check_oci_tooling() -> CheckResult:
    docker_path = shutil.which("docker")
    if docker_path is None:
        return CheckResult(
            "oci_tooling", False, "docker executable not found on PATH",
            "Install Docker and ensure it is on PATH.",
        )
    try:
        result = subprocess.run(
            ["docker", "version"], capture_output=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CheckResult(
            "oci_tooling", False, f"docker version failed: {exc}",
            "Ensure the Docker daemon is running.",
        )
    ok = result.returncode == 0
    detail = "docker version succeeded" if ok else "docker version returned non-zero"
    remedy = "" if ok else "Ensure the Docker daemon is running."
    return CheckResult("oci_tooling", ok, detail, remedy)


def _check_db_writable() -> CheckResult:
    settings = get_settings()
    directory = settings.db_path.parent if str(settings.db_path.parent) else "."
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=True):
            pass
    except OSError as exc:
        return CheckResult(
            "db_writable", False, f"Cannot write to {directory}: {exc}",
            f"Ensure {directory} exists and is writable.",
        )
    return CheckResult("db_writable", True, f"{directory} is writable", "")


def _check_disk_space() -> CheckResult:
    settings = get_settings()
    directory = settings.db_path.parent if str(settings.db_path.parent) else "."
    try:
        usage = shutil.disk_usage(directory)
    except OSError as exc:
        return CheckResult(
            "disk_space", False, f"Could not stat {directory}: {exc}",
            "Ensure the db_path directory exists on an accessible volume.",
        )
    free_gb = usage.free / (1024**3)
    ok = free_gb >= MIN_FREE_DISK_GB
    detail = f"{free_gb:.1f} GB free"
    remedy = "" if ok else f"Free at least {MIN_FREE_DISK_GB:.0f} GB on this volume."
    return CheckResult("disk_space", ok, detail, remedy)


_CHECKS = (
    _check_python_version,
    _check_nebius_credential,
    _check_contree_credential,
    _check_oci_tooling,
    _check_db_writable,
    _check_disk_space,
)


def run_doctor() -> int:
    console = Console()
    table = Table(title="falsegreen doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    all_ok = True
    failures: list[CheckResult] = []
    for check in _CHECKS:
        try:
            result = check()
        except Exception as exc:  # doctor must never crash
            result = CheckResult(check.__name__, False, f"check raised: {exc}", "Report this as a bug.")
        mark = "[green]PASS[/green]" if result.ok else "[red]FAIL[/red]"
        table.add_row(result.name, mark, result.detail)
        if not result.ok:
            all_ok = False
            failures.append(result)

    console.print(table)
    for failure in failures:
        console.print(f"  [red]FAIL {failure.name}[/red]: {failure.remedy}")

    return 0 if all_ok else 1
