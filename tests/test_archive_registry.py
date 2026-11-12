from pathlib import Path

import pytest

from pdfscrape.archive.registry import SourceRegistry, SourceRegistryError


def test_default_registry_includes_configured_public_sources():
    registry = SourceRegistry()
    enabled = registry.list_sources(enabled_only=True)
    assert set(enabled) == {"bcucluj", "internet_archive"}
    assert registry.get("bcucluj")["metadata_prefix"] == "xoai"


def test_registry_creates_adapter_without_network_access():
    registry = SourceRegistry()
    adapter = registry.create_adapter("bcucluj")
    assert adapter.source_id == "bcucluj"
    assert adapter.metadata_prefix == "xoai"


def test_registry_rejects_disabled_and_unknown_sources():
    registry = SourceRegistry()
    with pytest.raises(SourceRegistryError, match="disabled"):
        registry.create_adapter("gallica")
    with pytest.raises(SourceRegistryError, match="unknown archive source"):
        registry.get("not-configured")


def test_registry_rejects_invalid_source_config(tmp_path: Path):
    config_path = tmp_path / "sources.yaml"
    config_path.write_text("sources:\n  bad:\n    adapter: unknown\n", encoding="utf-8")
    with pytest.raises(SourceRegistryError, match="unsupported adapter"):
        SourceRegistry(config_path)
