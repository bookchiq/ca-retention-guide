"""Project settings: config.yaml plus secrets from the environment or .env.

The token is held in a field excluded from repr and is only handed to the API
client through `api_token()`. Nothing here logs or prints it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    raw: dict[str, Any]
    repo_root: Path
    contact_email: str | None
    _token: str | None = field(default=None, repr=False)

    def token_status(self) -> str:
        return "present" if self._token else "missing"

    def api_token(self) -> str:
        if not self._token:
            raise RuntimeError(
                "COURTLISTENER_TOKEN is not set. Add it to .env (see .env.example)."
            )
        return self._token

    def path(self, key: str) -> Path:
        return self.repo_root / self.raw["paths"][key]


def load(repo_root: Path | None = None) -> Settings:
    root = Path(repo_root) if repo_root else REPO_ROOT
    config_file = root / "config.yaml"
    raw = yaml.safe_load(config_file.read_text()) if config_file.exists() else {}
    env_file = dotenv_values(root / ".env") if (root / ".env").exists() else {}

    def secret(name: str) -> str | None:
        value = os.environ.get(name) or env_file.get(name)
        return value.strip() if value and value.strip() else None

    return Settings(
        raw=raw or {},
        repo_root=root,
        contact_email=secret("CL_CONTACT_EMAIL"),
        _token=secret("COURTLISTENER_TOKEN"),
    )
