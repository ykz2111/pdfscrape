"""Configuration management."""

import os
from pathlib import Path
from typing import Dict, Any
import yaml


class Config:
    """pdfscrape configuration."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path.home() / ".pdfscrape" / "config.yaml"
        self.config_path = config_path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self.data = yaml.safe_load(f) or {}

    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self.data, f)

    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.data[key] = value
        self.save()
