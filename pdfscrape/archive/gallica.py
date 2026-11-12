"""IIIF Presentation manifest adapter for individual Gallica documents."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from pdfscrape.archive.http import ArchiveHttpClient, ArchiveSourceError
from pdfscrape.archive.models import ArchiveRecord
from pdfscrape.archive.url_policy import build_copilot_url, canonicalize_public_url

_YEAR_RE = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")
_ARK_RE = re.compile(r"ark:/\d+/[^/?#]+", re.IGNORECASE)


class GallicaIiifAdapter:
    """Read IIIF Presentation 2/3 manifests supplied by public Gallica records."""

    def __init__(
        self,
        source_id: str = "gallica",
        http_client: ArchiveHttpClient | None = None,
    ):
        self.source_id = source_id
        self.http = http_client or ArchiveHttpClient()

    def get_record(self, manifest_url: str) -> ArchiveRecord:
        """Fetch a manifest URL and extract its descriptive metadata and files."""
        safe_manifest_url = canonicalize_public_url(manifest_url)
        try:
            payload = json.loads(self.http.get_bytes(safe_manifest_url).decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArchiveSourceError(
                f"IIIF manifest at {safe_manifest_url} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ArchiveSourceError(f"IIIF manifest at {safe_manifest_url} is not a JSON object")
        return self.record_from_manifest(payload, safe_manifest_url)

    def record_from_manifest(self, manifest: dict, manifest_url: str) -> ArchiveRecord:
        """Normalize an already-loaded IIIF Presentation manifest."""
        safe_manifest_url = canonicalize_public_url(manifest_url)
        metadata = _manifest_metadata(manifest)
        title = _first(metadata, "title", "dc.title") or _language_value(manifest.get("label"))
        title = title or "Untitled Gallica document"
        creators = _values(metadata, "creator", "dc.creator", "author")
        dates = _values(metadata, "date", "dc.date", "created", "year")
        year = _extract_year(dates)
        period = _first(metadata, "period", "temporal", "dc.coverage.temporal")
        language = _first(metadata, "language", "dc.language")
        rights = _first(metadata, "rights", "dc.rights") or _language_value(manifest.get("rights"))

        candidates: list[tuple[str, str, str]] = []
        _collect_resources(manifest.get("seeAlso"), candidates)
        _collect_resources(manifest.get("rendering"), candidates)
        _collect_resources(manifest.get("homepage"), candidates)
        pdf_url = next((url for url, kind, _ in candidates if kind == "pdf"), None)
        text_url = next((url for url, kind, _ in candidates if kind == "text"), None)
        landing_url = next((url for url, kind, _ in candidates if kind == "landing"), None)
        landing_url = landing_url or safe_manifest_url

        identifier = _first(metadata, "identifier", "dc.identifier", "ark")
        if not identifier:
            match = _ARK_RE.search(safe_manifest_url)
            identifier = match.group(0) if match else safe_manifest_url

        return ArchiveRecord(
            id=identifier,
            source_id=self.source_id,
            title=title,
            creators=creators,
            year=year,
            period=period,
            language=language,
            rights=rights,
            landing_url=landing_url,
            pdf_url=pdf_url,
            text_url=text_url,
            copilot_url=build_copilot_url(title, landing_url, year),
        )


def _manifest_metadata(manifest: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in manifest.get("metadata", []) if isinstance(manifest.get("metadata"), list) else []:
        if not isinstance(entry, dict):
            continue
        label = _language_value(entry.get("label"))
        value = _language_value(entry.get("value"))
        if label and value:
            result.setdefault(label.casefold(), []).append(value)
    return result


def _collect_resources(resources, output: list[tuple[str, str, str]]) -> None:
    if not resources:
        return
    entries = resources if isinstance(resources, list) else [resources]
    for entry in entries:
        if isinstance(entry, str):
            url = entry
            media_type = ""
            label = ""
        elif isinstance(entry, dict):
            url = entry.get("id") or entry.get("@id") or entry.get("url") or ""
            media_type = str(entry.get("format") or entry.get("type") or "").lower()
            label = _language_value(entry.get("label")) or ""
        else:
            continue
        if not url:
            continue
        safe_url = canonicalize_public_url(str(url))
        path = urlsplit(safe_url).path.lower()
        if "pdf" in media_type or path.endswith(".pdf"):
            kind = "pdf"
        elif any(token in media_type for token in ("text/plain", "alto", "xml")) or path.endswith(
            (".txt", ".xml", ".alto")
        ):
            kind = "text"
        elif "manifest" not in path:
            kind = "landing"
        else:
            kind = "manifest"
        output.append((safe_url, kind, label))


def _values(metadata: dict[str, list[str]], *labels: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for label in labels:
        for key, values in metadata.items():
            if key == label.casefold() or key.endswith("." + label.casefold()):
                for value in values:
                    if value not in seen:
                        seen.add(value)
                        result.append(value)
    return result


def _first(metadata: dict[str, list[str]], *labels: str) -> str | None:
    values = _values(metadata, *labels)
    return values[0] if values else None


def _language_value(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        return next((str(item).strip() for item in value if str(item).strip()), None)
    if isinstance(value, dict):
        for preferred in ("none", "ro", "en", "fr"):
            if preferred in value:
                result = _language_value(value[preferred])
                if result:
                    return result
        for item in value.values():
            result = _language_value(item)
            if result:
                return result
    return None


def _extract_year(values: list[str]) -> str | None:
    for value in values:
        match = _YEAR_RE.search(value)
        if match:
            return match.group(1)
    return None
