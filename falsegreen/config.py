from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FALSEGREEN_", extra="ignore")

    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    contree_token: SecretStr | None = None
    github_token: SecretStr | None = None
    backend: Literal["contree", "docker"] = "contree"
    max_concurrency: int = 50
    exec_timeout_multiplier: float = 4.0
    budget_usd_hard_stop: float = 250.0
    db_path: Path = Path("results.db")
    docs_dir: Path = Path("docs")
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
