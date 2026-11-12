"""OAI-PMH harvesting and Dublin Core / DSpace XOAI record normalization."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

from pdfscrape.archive.http import ArchiveHttpClient, ArchiveSourceError
from pdfscrape.archive.models import ArchiveRecord
from pdfscrape.archive.url_policy import UrlPolicyError, build_copilot_url, canonicalize_public_url

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)(1[5-9]\d{2}|20\d{2})(?!\d)")


class OaiPmhAdapter:
    """Harvest records from an OAI-PMH endpoint using ListRecords."""

    def __init__(
        self,
        endpoint: str,
        source_id: str,
        metadata_prefix: str = "oai_dc",
        set_spec: str | None = None,
        source_host: str | None = None,
        http_client: ArchiveHttpClient | None = None,
    ):
        self.endpoint = canonicalize_public_url(endpoint, source_host=source_host)
        self.source_id = source_id
        self.metadata_prefix = metadata_prefix
        self.set_spec = set_spec
        self.source_host = source_host
        self.http = http_client or ArchiveHttpClient()
        if not source_id.strip():
            raise ValueError("source_id must not be empty")
        if not metadata_prefix.strip():
            raise ValueError("metadata_prefix must not be empty")

    def harvest(
        self,
        from_date: str | None = None,
        until: str | None = None,
        max_records: int | None = None,
    ) -> list[ArchiveRecord]:
        """Fetch OAI-PMH pages until exhausted or ``max_records`` is reached."""
        if max_records is not None and max_records < 1:
            raise ValueError("max_records must be greater than zero")

        records: list[ArchiveRecord] = []
        token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            params = {"verb": "ListRecords"}
            if token:
                params["resumptionToken"] = token
            else:
                params["metadataPrefix"] = self.metadata_prefix
                if self.set_spec:
                    params["set"] = self.set_spec
                if from_date:
                    params["from"] = from_date
                if until:
                    params["until"] = until

            try:
                response = self.http.get_bytes(
                    self._request_url(params), source_host=self.source_host
                )
                root = _parse_xml(response)
            except UrlPolicyError:
                raise
            except ArchiveSourceError:
                raise

            oai_error = next(
                (node for node in root.iter() if _local_name(node.tag) == "error"), None
            )
            if oai_error is not None:
                code = oai_error.attrib.get("code", "unknown")
                message = " ".join((oai_error.text or "").split())
                if code == "noRecordsMatch":
                    break
                raise ArchiveSourceError(f"OAI-PMH {code}: {message or 'request failed'}")

            for node in root.iter():
                if _local_name(node.tag) != "record":
                    continue
                header = next((child for child in node if _local_name(child.tag) == "header"), None)
                if header is None or header.attrib.get("status") == "deleted":
                    continue
                metadata = next(
                    (child for child in node if _local_name(child.tag) == "metadata"), None
                )
                identifier = _first_text(header, "identifier")
                if not identifier:
                    raise ArchiveSourceError("OAI-PMH record is missing its header identifier")
                record = _record_from_metadata(
                    metadata,
                    identifier=identifier,
                    source_id=self.source_id,
                    source_host=self.source_host,
                )
                records.append(record)
                if max_records is not None and len(records) >= max_records:
                    return records

            token_node = next(
                (node for node in root.iter() if _local_name(node.tag) == "resumptionToken"),
                None,
            )
            token = (token_node.text or "").strip() if token_node is not None else ""
            if not token:
                break
            if token in seen_tokens:
                raise ArchiveSourceError("OAI-PMH endpoint repeated a resumption token")
            seen_tokens.add(token)
        return records

    def _request_url(self, params: dict[str, str]) -> str:
        parts = urlsplit(self.endpoint)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(params)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )


def _parse_xml(payload: bytes) -> ET.Element:
    normalized = payload.replace(b"\x00", b"").upper()
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", normalized):
        raise ArchiveSourceError("OAI-PMH response contains a forbidden DTD or entity declaration")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ArchiveSourceError(f"OAI-PMH response is not valid XML: {exc}") from exc


def _record_from_metadata(
    metadata: ET.Element | None,
    identifier: str,
    source_id: str,
    source_host: str | None,
) -> ArchiveRecord:
    values: dict[str, list[str]] = defaultdict(list)
    urls: list[str] = []
    checksum_values: list[str] = []
    if metadata is not None:
        _collect_metadata(metadata, values)
        for node in metadata.iter():
            for key, value in node.attrib.items():
                if key.rsplit("}", 1)[-1].lower() in {"url", "href", "uri", "downloadurl"}:
                    urls.extend(_extract_urls(value))
            urls.extend(_extract_urls(node.text or ""))
            for key in node.attrib:
                if key.rsplit("}", 1)[-1].lower() in {"checksum", "md5", "sha1"}:
                    checksum_values.extend(
                        _extract_urls(node.attrib[key]) or [node.attrib[key].strip()]
                    )
        for key, items in values.items():
            if any(part in key for part in ("checksum", "md5", "sha1")):
                checksum_values.extend(items)

    title = _first_value(values, "title") or identifier
    creators = _distinct_values(values, ("creator", "contributor.author"))
    dates = _distinct_values(values, ("date.issued", "date.created", "date", "year"))
    year = _extract_year(dates)
    period = _first_value(values, "coverage.temporal", "temporal", "period")
    language = _first_value(values, "language.iso", "language")
    rights = _first_value(values, "rights", "rights.uri", "license")

    public_urls: list[str] = []
    seen_urls: set[str] = set()
    for candidate in urls:
        try:
            public_url = canonicalize_public_url(candidate, source_host=source_host)
        except UrlPolicyError as exc:
            raise ArchiveSourceError(
                f"unsafe document URL in OAI record {identifier!r}: {exc}"
            ) from exc
        if public_url not in seen_urls:
            seen_urls.add(public_url)
            public_urls.append(public_url)

    bitstreams = _xoai_bitstreams(metadata) if metadata is not None else []
    source_base = _source_base_url(source_host)
    handle = next(
        (value for value in (_dspace_handle(url) for url in public_urls) if value),
        None,
    )
    for bitstream in bitstreams:
        raw_url = bitstream.get("url")
        if raw_url and raw_url.startswith("/") and source_base:
            raw_url = urljoin(source_base, raw_url)
        if not raw_url and bitstream.get("name") and handle and source_base:
            query = urlencode({"sequence": bitstream.get("sequence", "1"), "isAllowed": "y"})
            raw_url = (
                f"{source_base}/bitstream/handle/{quote(handle, safe='/')}/"
                f"{quote(bitstream['name'], safe='')}?{query}"
            )
        if not raw_url:
            continue
        try:
            public_url = canonicalize_public_url(raw_url, source_host=source_host)
        except UrlPolicyError as exc:
            raise ArchiveSourceError(
                f"unsafe bitstream URL in OAI record {identifier!r}: {exc}"
            ) from exc
        if public_url not in seen_urls:
            seen_urls.add(public_url)
            public_urls.append(public_url)

    pdf_url = next((url for url in public_urls if _is_pdf_url(url)), None)
    text_url = next((url for url in public_urls if _is_text_url(url)), None)
    landing_url = next(
        (url for url in public_urls if url not in {pdf_url, text_url}),
        None,
    )
    checksum = next((value.strip() for value in checksum_values if value.strip()), None)
    handoff_target = landing_url or pdf_url or text_url
    copilot_url = build_copilot_url(title, handoff_target, year) if handoff_target else None

    return ArchiveRecord(
        id=identifier,
        source_id=source_id,
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


def _collect_metadata(root: ET.Element, values: dict[str, list[str]]) -> None:
    """Collect Dublin Core fields and nested DSpace XOAI element paths."""
    for node in root.iter():
        name = _local_name(node.tag).lower()
        if name == "field" and node.attrib.get("element"):
            parts = [node.attrib.get("mdschema", ""), node.attrib["element"]]
            qualifier = node.attrib.get("qualifier")
            if qualifier and qualifier.lower() not in {"none", "unspecified"}:
                parts.append(qualifier)
            key = ".".join(part.lower() for part in parts if part)
            text = " ".join((node.text or "").split())
            if key and text:
                values[key].append(text)

    def visit(node: ET.Element, ancestors: list[str]) -> None:
        name = node.attrib.get("name", "").lower()
        path = ancestors + ([name] if name else [])
        text = " ".join((node.text or "").split())
        if text and path:
            normalized = [
                part
                for part in path
                if part not in {"metadata", "dim", "xoai", "none", "unspecified"}
            ]
            if normalized:
                values[".".join(normalized)].append(text)
                values[normalized[-1]].append(text)
        for child in node:
            visit(child, path if name else ancestors)

    visit(root, [])


def _xoai_bitstreams(root: ET.Element) -> list[dict[str, str]]:
    """Extract bitstream names, direct links, sequence numbers, and checksums."""
    bitstreams = []
    link_names = {"url", "uri", "href", "downloadurl", "retrievelink", "link"}
    for node in root.iter():
        if (
            _local_name(node.tag).lower() != "element"
            or node.attrib.get("name", "").lower() != "bitstream"
        ):
            continue
        details: dict[str, str] = {}
        for child in node.iter():
            key = child.attrib.get("name", _local_name(child.tag)).lower().replace("_", "")
            text = " ".join((child.text or "").split())
            if not text:
                continue
            if key == "name" and "name" not in details:
                details["name"] = text
            elif key in {"sequenceid", "sequence"} and "sequence" not in details:
                details["sequence"] = text
            elif key in link_names and "url" not in details:
                details["url"] = text
            elif key in {"checksum", "md5", "sha1"} and "checksum" not in details:
                details["checksum"] = text
        if details:
            bitstreams.append(details)
    return bitstreams


def _source_base_url(source_host: str | None) -> str | None:
    if not source_host:
        return None
    value = source_host.strip()
    if "://" not in value:
        value = f"https://{value}"
    return canonicalize_public_url(value).rstrip("/")


def _dspace_handle(url: str) -> str | None:
    path = urlsplit(url).path
    if "/bitstream/" in path:
        return None
    segments = [segment for segment in path.split("/") if segment]
    try:
        index = segments.index("handle")
    except ValueError:
        return None
    handle = "/".join(segments[index + 1 :])
    return handle or None


def _extract_urls(value: str) -> list[str]:
    urls = []
    for match in _URL_RE.findall(value):
        urls.append(match.rstrip(".,;)]}"))
    return urls


def _extract_year(values: list[str]) -> str | None:
    for value in values:
        match = _YEAR_RE.search(value)
        if match:
            return match.group(1)
    return None


def _first_value(values: dict[str, list[str]], *suffixes: str) -> str | None:
    for suffix in suffixes:
        for key, items in values.items():
            if key == suffix or key.endswith("." + suffix):
                for item in items:
                    if item.strip():
                        return item.strip()
    return None


def _distinct_values(values: dict[str, list[str]], suffixes: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for suffix in suffixes:
        for key, items in values.items():
            if key == suffix or key.endswith("." + suffix):
                for item in items:
                    value = item.strip()
                    if value and value not in seen:
                        seen.add(value)
                        result.append(value)
    return result


def _is_pdf_url(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".pdf")


def _is_text_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith((".txt", ".text"))


def _first_text(node: ET.Element, child_name: str) -> str | None:
    child = next((item for item in node if _local_name(item.tag) == child_name), None)
    return " ".join((child.text or "").split()) if child is not None and child.text else None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]
