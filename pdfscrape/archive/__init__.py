"""Key-free harvesting and static cataloguing of Romanian historical PDFs."""

from __future__ import annotations

from pdfscrape.archive.url_policy import (
    UrlPolicyError,
    build_copilot_url,
    canonicalize_public_url,
)

__all__ = ["UrlPolicyError", "build_copilot_url", "canonicalize_public_url"]
