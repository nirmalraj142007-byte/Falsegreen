from __future__ import annotations

from falsegreen.config import get_settings
from falsegreen.errors import ConfigError, MissingCredential
from falsegreen.sandbox.base import SandboxBackend
from falsegreen.sandbox.docker_backend import DockerBackend


def get_backend(name: str | None = None) -> SandboxBackend:
    settings = get_settings()
    backend_name = name or settings.backend

    if backend_name == "docker":
        return DockerBackend()

    if backend_name == "contree":
        if settings.contree_token is None:
            raise MissingCredential(
                "Contree backend requested but FALSEGREEN_CONTREE_TOKEN is not set. "
                "Request Early Access at contree.dev and set the token, or pass "
                "--backend docker for local development."
            )
        raise NotImplementedError(
            "Contree backend integration is pending Early Access (see DECISIONS.md U-05); "
            "use the docker backend until it lands."
        )

    raise ConfigError(f"Unknown sandbox backend '{backend_name}'. Valid backends: docker, contree.")
