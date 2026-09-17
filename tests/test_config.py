from __future__ import annotations

from falsegreen.config import Settings, get_settings


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.backend == "contree"
    assert settings.max_concurrency == 50
    assert settings.nebius_api_key is None


def test_env_prefix_is_respected(monkeypatch) -> None:
    monkeypatch.setenv("FALSEGREEN_MAX_CONCURRENCY", "7")
    settings = Settings(_env_file=None)
    assert settings.max_concurrency == 7


def test_unprefixed_env_var_is_ignored(monkeypatch) -> None:
    monkeypatch.setenv("MAX_CONCURRENCY", "999")
    settings = Settings(_env_file=None)
    assert settings.max_concurrency == 50
