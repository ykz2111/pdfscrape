"""Catalog validation and static archival site builder."""

from __future__ import annotations

import dataclasses
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, urlsplit

from pdfscrape.archive.url_policy import (
    COPILOT_BASE_URL,
    UrlPolicyError,
    build_copilot_url,
    canonicalize_public_url,
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSET_FILES = ("tokens.css", "styles.css", "app.js", "index.html")
DEFAULT_SITE_TITLE = "Romanian Historical PDF Archive"
_PROMPT_SOURCE_RE = re.compile(r"Source:\s*(\S+)")


class CatalogValidationError(ValueError):
    """Raised when catalog records fail URL policy or schema validation."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(
            f"Catalog validation failed: {report.invalid} invalid of {report.total} records"
        )


@dataclasses.dataclass(frozen=True)
class ValidationIssue:
    """Single validation failure on a catalog record."""

    record_id: str
    field: str
    reason: str
    detail: str
    url: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "record_id": self.record_id,
            "field": self.field,
            "reason": self.reason,
            "detail": self.detail,
            "url": self.url,
        }


@dataclasses.dataclass
class ValidationReport:
    """Summary of catalog validation results."""

    total: int
    valid: int
    invalid: int
    issues: list[ValidationIssue]

    @property
    def ok(self) -> bool:
        return self.invalid == 0 and len(self.issues) == 0

    def grouped_reasons(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.reason] = counts.get(issue.reason, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total": self.total,
            "valid": self.valid,
            "invalid": self.invalid,
            "reasons": self.grouped_reasons(),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclasses.dataclass(frozen=True)
class BuildResult:
    """Output metadata from StaticSiteBuilder.build()."""

    output_dir: Path
    catalog_path: Path
    index_path: Path
    record_count: int
    skipped_count: int
    files: tuple[Path, ...]


def _as_mapping(record: Any) -> Mapping[str, Any]:
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        return dataclasses.asdict(record)
    if isinstance(record, Mapping):
        return record
    raise TypeError(f"Expected a mapping or dataclass record, got {type(record).__name__}")


def load_catalog_records(path: Path) -> list[dict[str, Any]]:
    """Load catalog records from a JSONL or JSON file."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Catalog file not found: {source}")

    raw = source.read_text(encoding="utf-8")
    stripped = raw.strip()
    if not stripped:
        return []

    if source.suffix.lower() == ".json" or stripped.startswith("[") or (
        stripped.startswith("{") and "\n" not in stripped and '"records"' in stripped
    ):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {source}: {exc}") from exc
        if isinstance(payload, list):
            return [dict(_as_mapping(item)) for item in payload]
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return [dict(_as_mapping(item)) for item in payload["records"]]
        raise ValueError(f"Unsupported JSON catalog structure in {source}")

    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        try:
            item = json.loads(line_stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {source}:{lineno}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"Expected JSON object at {source}:{lineno}")
        records.append(item)
    return records


def _validate_copilot_link(copilot_url: str, record_id: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        canonical = canonicalize_public_url(copilot_url)
    except UrlPolicyError as exc:
        return [ValidationIssue(record_id, "copilot_url", exc.reason, exc.detail, copilot_url)]

    parts = urlsplit(canonical)
    if not canonical.startswith(COPILOT_BASE_URL):
        issues.append(
            ValidationIssue(
                record_id,
                "copilot_url",
                "copilot_host",
                f"copilot_url must target {COPILOT_BASE_URL}",
                copilot_url,
            )
        )
        return issues

    prompts = parse_qs(parts.query).get("prompt", [])
    if not prompts or not prompts[0].strip():
        issues.append(
            ValidationIssue(
                record_id,
                "copilot_url",
                "copilot_prompt",
                "copilot_url is missing a prompt parameter",
                copilot_url,
            )
        )
        return issues

    match = _PROMPT_SOURCE_RE.search(prompts[0])
    if match:
        embedded_source = match.group(1)
        try:
            canonicalize_public_url(embedded_source)
        except UrlPolicyError as exc:
            issues.append(
                ValidationIssue(
                    record_id,
                    "copilot_url",
                    exc.reason,
                    f"embedded Source URL failed policy: {exc.detail}",
                    embedded_source,
                )
            )
    return issues


def validate_record(record: Any, index: int = 0) -> list[ValidationIssue]:
    """Validate a single catalog record and return any policy/schema issues."""
    data = _as_mapping(record)
    record_id = str(data.get("id") or f"record-{index}")
    issues: list[ValidationIssue] = []

    if not str(data.get("title") or "").strip():
        issues.append(
            ValidationIssue(record_id, "title", "missing_field", "title is required")
        )
    if not str(data.get("source_id") or "").strip():
        issues.append(
            ValidationIssue(record_id, "source_id", "missing_field", "source_id is required")
        )

    source_host = data.get("source_host")
    landing_url = data.get("landing_url")
    if not landing_url or not str(landing_url).strip():
        issues.append(
            ValidationIssue(record_id, "landing_url", "missing_field", "landing_url is required")
        )
    else:
        try:
            canonicalize_public_url(str(landing_url), source_host=source_host)
        except UrlPolicyError as exc:
            issues.append(
                ValidationIssue(
                    record_id, "landing_url", exc.reason, exc.detail, str(landing_url)
                )
            )

    for url_field in ("pdf_url", "text_url"):
        raw_val = data.get(url_field)
        if raw_val:
            try:
                canonicalize_public_url(str(raw_val), source_host=source_host)
            except UrlPolicyError as exc:
                issues.append(
                    ValidationIssue(record_id, url_field, exc.reason, exc.detail, str(raw_val))
                )

    copilot_url = data.get("copilot_url")
    if copilot_url:
        issues.extend(_validate_copilot_link(str(copilot_url), record_id))

    return issues


def validate_catalog(records: Iterable[Any]) -> ValidationReport:
    """Validate every record in a catalog iterable."""
    record_list = list(records)
    all_issues: list[ValidationIssue] = []
    invalid_count = 0

    for idx, rec in enumerate(record_list):
        rec_issues = validate_record(rec, index=idx)
        if rec_issues:
            invalid_count += 1
            all_issues.extend(rec_issues)

    total = len(record_list)
    return ValidationReport(
        total=total,
        valid=total - invalid_count,
        invalid=invalid_count,
        issues=all_issues,
    )


def sanitize_record(record: Any) -> dict[str, Any]:
    """Canonicalize all URLs and construct a clean JSON-serializable catalog record."""
    data = dict(_as_mapping(record))
    source_host = data.get("source_host")

    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("Record title must not be empty")

    source_id = str(data.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("Record source_id must not be empty")

    landing_url = canonicalize_public_url(str(data["landing_url"]), source_host=source_host)
    pdf_url = (
        canonicalize_public_url(str(data["pdf_url"]), source_host=source_host)
        if data.get("pdf_url")
        else None
    )
    text_url = (
        canonicalize_public_url(str(data["text_url"]), source_host=source_host)
        if data.get("text_url")
        else None
    )

    year = str(data["year"]).strip() if data.get("year") is not None else None
    if year == "":
        year = None

    raw_creators = data.get("creators") or []
    if isinstance(raw_creators, str):
        creators = [raw_creators.strip()] if raw_creators.strip() else []
    else:
        creators = [str(c).strip() for c in raw_creators if str(c).strip()]

    primary_url = pdf_url or landing_url
    copilot_url = build_copilot_url(title, primary_url, year=year)

    return {
        "id": str(data.get("id") or f"{source_id}:{primary_url}"),
        "source_id": source_id,
        "source_name": str(data.get("source_name") or source_id),
        "title": title,
        "creators": creators,
        "year": year,
        "period": str(data["period"]).strip() if data.get("period") else None,
        "language": str(data["language"]).strip() if data.get("language") else None,
        "rights": str(data["rights"]).strip() if data.get("rights") else None,
        "landing_url": landing_url,
        "pdf_url": pdf_url,
        "text_url": text_url,
        "checksum": str(data["checksum"]).strip() if data.get("checksum") else None,
        "summary": str(data["summary"]).strip() if data.get("summary") else None,
        "excerpt": str(data["excerpt"]).strip() if data.get("excerpt") else None,
        "copilot_url": copilot_url,
    }


class StaticSiteBuilder:
    """Builds the static archival catalog site (HTML, CSS, JS, and catalog.json)."""

    def __init__(self, assets_dir: Path | None = None) -> None:
        self.assets_dir = Path(assets_dir) if assets_dir else ASSETS_DIR

    def build(
        self,
        records: Iterable[Any],
        output_dir: Path,
        *,
        title: str = DEFAULT_SITE_TITLE,
        strict: bool = True,
    ) -> BuildResult:
        """Validate records, emit catalog.json, and copy static UI assets."""
        record_list = list(records)
        if strict:
            report = validate_catalog(record_list)
            if not report.ok:
                raise CatalogValidationError(report)

        sanitized: list[dict[str, Any]] = []
        skipped = 0
        for idx, rec in enumerate(record_list):
            if not strict and validate_record(rec, index=idx):
                skipped += 1
                continue
            sanitized.append(sanitize_record(rec))

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        catalog_path = out / "catalog.json"
        catalog_path.write_text(
            json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        written_files: list[Path] = [catalog_path]
        escaped_title = html.escape(title, quote=True)

        for filename in ASSET_FILES:
            src_file = self.assets_dir / filename
            if not src_file.is_file():
                raise FileNotFoundError(f"Missing static UI asset: {src_file}")
            dst_file = out / filename
            if filename == "index.html":
                content = src_file.read_text(encoding="utf-8")
                content = content.replace("<!--SITE_TITLE-->", escaped_title)
                dst_file.write_text(content, encoding="utf-8")
            else:
                shutil.copy2(src_file, dst_file)
            written_files.append(dst_file)

        nojekyll_path = out / ".nojekyll"
        nojekyll_path.write_text("", encoding="utf-8")
        written_files.append(nojekyll_path)

        return BuildResult(
            output_dir=out,
            catalog_path=catalog_path,
            index_path=out / "index.html",
            record_count=len(sanitized),
            skipped_count=skipped,
            files=tuple(written_files),
        )


__all__ = [
    "ASSETS_DIR",
    "BuildResult",
    "CatalogValidationError",
    "DEFAULT_SITE_TITLE",
    "StaticSiteBuilder",
    "ValidationIssue",
    "ValidationReport",
    "load_catalog_records",
    "sanitize_record",
    "validate_catalog",
    "validate_record",
]
