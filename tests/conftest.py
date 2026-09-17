from __future__ import annotations

import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "version"], capture_output=True, timeout=5, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _docker_available():
        return
    skip_marker = pytest.mark.skip(reason="Docker is not available in this environment.")
    for item in items:
        if "requires_docker" in item.keywords:
            item.add_marker(skip_marker)
