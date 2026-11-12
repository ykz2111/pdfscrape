"""Key-free harvesting and static cataloguing of Romanian historical PDFs."""

from __future__ import annotations

from pdfscrape.archive.models import ArchiveRecord
from pdfscrape.archive.registry import SourceRegistry
from pdfscrape.archive.site import (
    BuildResult,
    CatalogValidationError,
    StaticSiteBuilder,
    ValidationIssue,
    ValidationReport,
    load_catalog_records,
    sanitize_record,
    validate_catalog,
    validate_record,
)
from pdfscrape.archive.url_policy import (
    UrlPolicyError,
    build_copilot_url,
    canonicalize_public_url,
)

__all__ = [
    "ArchiveRecord",
    "BuildResult",
    "CatalogValidationError",
    "SourceRegistry",
    "StaticSiteBuilder",
    "UrlPolicyError",
    "ValidationIssue",
    "ValidationReport",
    "build_copilot_url",
    "canonicalize_public_url",
    "load_catalog_records",
    "sanitize_record",
    "validate_catalog",
    "validate_record",
]
