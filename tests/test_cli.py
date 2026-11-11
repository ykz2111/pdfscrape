"""Tests for provider routing and config handling."""

from pdfscrape.chat import resolve_providers
from pdfscrape.config import Config
from pdfscrape.providers import provider_names


def test_resolve_auto():
    assert resolve_providers(None) == ["auto"]
    assert resolve_providers("auto") == ["auto"]


def test_resolve_single():
    assert resolve_providers("codex") == ["codex"]


def test_resolve_list():
    assert resolve_providers("codex,claude") == ["codex", "claude"]


def test_resolve_all():
    assert resolve_providers("all") == provider_names()


def test_config_defaults():
    config = Config(path=None)
    # Defaults must survive an absent config file.
    assert config.get("chat.default_provider") == "auto"


def test_config_model_for():
    config = Config()
    assert config.model_for("codex") == "gpt-6.1-sol"
    assert config.model_for("ollama") == "smollm2:latest"
