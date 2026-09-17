from __future__ import annotations

import pytest

from falsegreen.config import get_settings
from falsegreen.errors import ConfigError
from falsegreen.sandbox.docker_backend import DockerBackend
from falsegreen.sandbox.factory import get_backend


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_contree_without_token_raises_config_error(monkeypatch) -> None:
    monkeypatch.delenv("FALSEGREEN_CONTREE_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        get_backend("contree")


def test_docker_backend_returned_for_docker_name() -> None:
    backend = get_backend("docker")
    assert isinstance(backend, DockerBackend)
    assert backend.name == "docker"


def test_unknown_backend_name_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        get_backend("not-a-real-backend")


def test_defaults_to_settings_backend(monkeypatch) -> None:
    monkeypatch.setenv("FALSEGREEN_BACKEND", "docker")
    backend = get_backend()
    assert isinstance(backend, DockerBackend)
