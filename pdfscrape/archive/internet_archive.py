"""Adapter for Internet Archive's unauthenticated Advanced Search and metadata APIs."""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlencode

from pdfscrape.archive.http import ArchiveHttpClient, ArchiveSourceError
from pdfscrape.archive.models import ArchiveRecord
from pdfscrape.archive.url_policy import build_copilot_url, canonicalize_public_url

DEFAULT_QUERY = "language:rum AND mediatype:texts"
_YEAR_RE = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class InternetArchiveAdapter:
    """Search and read public Internet Archive text item metadata."""

    def __init__(
        self,
        source_id: str = "internet_archive",
        base_url: str = "https://archive.org",
        query: str = DEFAULT_QUERY,
        http_client: ArchiveHttpClient | None = None,
    ):
        self.source_id = source_id
        self.base_url = canonicalize_public_url(base_url).rstrip("/")
        self.query = query
        self.http = http_client or ArchiveHttpClient()

    def harvest(self, max_records: int = 100, rows_per_page: int = 50) -> list[ArchiveRecord]:
        """Fetch matching items in stable, bounded pages."""
        if max_records < 1:
            raise ValueError("max_records must be greater than zero")
        if rows_per_page < 1 or rows_per_page > 100:
            raise ValueError("rows_per_page must be between 1 and 100")

        records: list[ArchiveRecord] = []
        page = 1
        while len(records) < max_records:
            page_size = min(rows_per_page, max_records - len(records))
            payload = self._get_json(
                self._url(
                    "advancedsearch.php",
                    {
                        "q": self.query,
                        "fl[]": "identifier",
                        "rows": page_size,
                        "page": page,
                        "output": "json",
                    },
                )
            )
            response = payload.get("response", {})
            docs = response.get("docs", [])
            if not isinstance(docs, list) or not docs:
                break
            for doc in docs:
                identifier = _first(doc.get("identifier"))
                if not identifier:
                    continue
                records.append(self.get_record(identifier))
                if len(records) >= max_records:
                    break
            total = response.get("numFound")
            if len(docs) < page_size or (isinstance(total, int) and page * page_size >= total):
                break
            page += 1
        return records

    def get_record(self, identifier: str) -> ArchiveRecord:
        """Read one public metadata JSON document and normalize its files."""
        if not _IDENTIFIER_RE.fullmatch(identifier):
            raise ValueError("Internet Archive identifier contains unsupported characters")
        payload = self._get_json(f"{self.base_url}/metadata/{quote(identifier, safe='')}")
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ArchiveSourceError(f"Internet Archive metadata for {identifier!r} is malformed")

        landing_url = canonicalize_public_url(
            f"{self.base_url}/details/{quote(identifier, safe='')}"
        )
        files = payload.get("files", [])
        if not isinstance(files, list):
            files = []
        pdf_url = None
        text_url = None
        checksum = None
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            name = str(file_info.get("name", ""))
            fmt = str(file_info.get("format", "")).lower()
            lowered_name = name.lower()
            file_url = (
                canonicalize_public_url(
                    f"{self.base_url}/download/{quote(identifier, safe='')}/{quote(name, safe='/')}"
                )
                if name
                else None
            )
            if file_url and pdf_url is None and (lowered_name.endswith(".pdf") or fmt == "pdf"):
                pdf_url = file_url
                checksum = _checksum(file_info)
            if (
                file_url
                and text_url is None
                and (lowered_name.endswith((".txt", ".text")) or fmt in {"text", "text/plain"})
            ):
                text_url = file_url
                checksum = checksum or _checksum(file_info)

        title = _first(metadata.get("title")) or identifier
        creators = _as_values(metadata.get("creator"))
        dates = _as_values(metadata.get("date")) + _as_values(metadata.get("year"))
        year = _extract_year(dates)
        period = _first(metadata.get("coverage")) or _first(metadata.get("temporal"))
        language = _first(metadata.get("language"))
        rights = _first(metadata.get("rights")) or _first(metadata.get("licenseurl"))
        copilot_url = build_copilot_url(title, landing_url, year)
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
            checksum=checksum,
            copilot_url=copilot_url,
        )

    def _get_json(self, url: str) -> dict:
        try:
            payload = json.loads(self.http.get_bytes(url).decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArchiveSourceError(f"Internet Archive returned invalid JSON for {url}") from exc
        if not isinstance(payload, dict):
            raise ArchiveSourceError(
                f"Internet Archive returned an unexpected JSON value for {url}"
            )
        return payload

    def _url(self, path: str, params: dict) -> str:
        return f"{self.base_url}/{path}?{urlencode(params, doseq=True)}"


def _as_values(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _first(value) -> str | None:
    values = _as_values(value)
    return values[0] if values else None


def _extract_year(values: list[str]) -> str | None:
    for value in values:
        match = _YEAR_RE.search(value)
        if match:
            return match.group(1)
    return None


def _checksum(file_info: dict) -> str | None:
    for key in ("sha1", "md5"):
        value = file_info.get(key)
        if value:
            return str(value)
    return None
