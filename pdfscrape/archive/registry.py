"""Declarative source configuration and adapter factory."""

from __future__ import annotations

from pathlib import Path

import yaml


class SourceRegistryError(ValueError):
    """Raised when a source configuration is invalid or unavailable."""


class SourceRegistry:
    """Load source definitions and instantiate their corresponding adapters."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(__file__).with_name("sources.yaml")
        self.sources = self._load()

    def _load(self) -> dict[str, dict]:
        try:
            with self.path.open(encoding="utf-8") as stream:
                document = yaml.safe_load(stream) or {}
        except OSError as exc:
            raise SourceRegistryError(
                f"could not read archive sources from {self.path}: {exc}"
            ) from exc
        except yaml.YAMLError as exc:
            raise SourceRegistryError(f"invalid YAML in {self.path}: {exc}") from exc
        sources = document.get("sources") if isinstance(document, dict) else None
        if not isinstance(sources, dict):
            raise SourceRegistryError("sources.yaml must contain a 'sources' mapping")
        normalized: dict[str, dict] = {}
        for source_id, config in sources.items():
            if (
                not isinstance(source_id, str)
                or not source_id.strip()
                or not isinstance(config, dict)
            ):
                raise SourceRegistryError(
                    "each source must have a non-empty name and mapping config"
                )
            if config.get("adapter") not in {"oai", "internet_archive", "gallica_iiif"}:
                raise SourceRegistryError(f"source {source_id!r} has an unsupported adapter")
            normalized[source_id] = dict(config)
        return normalized

    def list_sources(self, enabled_only: bool = False) -> dict[str, dict]:
        """Return source definitions, optionally limited to enabled sources."""
        selected = {
            name: dict(config)
            for name, config in self.sources.items()
            if not enabled_only or config.get("enabled", False)
        }
        return selected

    def get(self, source_id: str) -> dict:
        """Return one source definition or an actionable configuration error."""
        try:
            return dict(self.sources[source_id])
        except KeyError as exc:
            available = ", ".join(sorted(self.sources)) or "none"
            raise SourceRegistryError(
                f"unknown archive source {source_id!r}; configured sources: {available}"
            ) from exc

    def create_adapter(self, source_id: str, **overrides):
        """Instantiate a configured adapter without performing network access."""
        config = self.get(source_id)
        if not config.get("enabled", False):
            raise SourceRegistryError(f"archive source {source_id!r} is disabled in {self.path}")
        config.update(overrides)
        adapter_type = config.pop("adapter")
        config.pop("enabled", None)
        if adapter_type == "oai":
            from pdfscrape.archive.oai import OaiPmhAdapter

            return OaiPmhAdapter(source_id=source_id, **config)
        if adapter_type == "internet_archive":
            from pdfscrape.archive.internet_archive import InternetArchiveAdapter

            return InternetArchiveAdapter(source_id=source_id, **config)
        from pdfscrape.archive.gallica import GallicaIiifAdapter

        return GallicaIiifAdapter(source_id=source_id, **config)
