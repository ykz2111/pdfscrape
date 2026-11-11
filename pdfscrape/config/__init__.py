"""Configuration handling."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".pdfscrape"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"

DEFAULTS: dict[str, Any] = {
    "providers": {
        "codex": {"model": "gpt-6.1-sol"},
        "claude": {"model": None},
        "antigravity": {"model": "gemini-3.8-flash-high"},
        "copilot": {"model": None},
        "gitlab": {"model": None},
        "ollama": {"model": "smollm2:latest"},
    },
    "chat": {
        "default_provider": "auto",
        "timeout": 600,
    },
    "logging": {
        "level": "INFO",
    },
}


class Config:
    """YAML config with env overrides."""

    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_CONFIG_PATH
        self.data = self._deep_merge(DEFAULTS, self._load())

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as fh:
                return yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            return {}

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = dict(base)
        for key, value in (override or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, path: str, default: Any = None) -> Any:
        """Read a dotted config path."""
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        """Write a dotted config path and persist it."""
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self.save()

    def save(self) -> None:
        """Persist the config to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as fh:
            yaml.safe_dump(self.data, fh, sort_keys=False)

    def model_for(self, provider: str) -> str | None:
        """Configured model for a provider."""
        return self.get(f"providers.{provider}.model")

    def env_override(self, provider: str) -> str | None:
        """PDFSCRAPE_<PROVIDER>_MODEL env override."""
        key = f"PDFSCRAPE_{provider.upper().replace('-', '_')}_MODEL"
        return os.environ.get(key)
