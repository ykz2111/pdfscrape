"""Small, polite HTTP client for public archive protocols."""

from __future__ import annotations

import email.utils
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from pdfscrape.archive.url_policy import UrlPolicyError, canonicalize_public_url


class ArchiveSourceError(RuntimeError):
    """Raised when an archive source request or response is invalid."""


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate and normalize every redirect before urllib follows it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url = canonicalize_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


class ArchiveHttpClient:
    """Synchronous HTTP client with URL checks, pacing, and transient retries."""

    def __init__(
        self,
        user_agent: str = "pdfscrape-archive/0.1 (+https://github.com/)",
        timeout_seconds: float = 30.0,
        min_delay_seconds: float = 1.0,
        max_retries: int = 3,
        max_response_bytes: int = 20 * 1024 * 1024,
        opener=None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if min_delay_seconds < 0:
            raise ValueError("min_delay_seconds must not be negative")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.min_delay_seconds = min_delay_seconds
        self.max_retries = max_retries
        self.max_response_bytes = max_response_bytes
        self._opener = opener or urllib.request.build_opener(_SafeRedirectHandler())
        self._last_request_at = 0.0

    def get_bytes(self, url: str, source_host: str | None = None) -> bytes:
        """Fetch a URL after validating it, retrying temporary upstream failures."""
        safe_url = canonicalize_public_url(url, source_host=source_host)
        request = urllib.request.Request(
            safe_url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/xml, application/json, */*",
            },
        )

        for attempt in range(self.max_retries + 1):
            self._pace()
            try:
                with self._opener.open(request, timeout=self.timeout_seconds) as response:
                    body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise ArchiveSourceError(
                        f"response from {safe_url} exceeds {self.max_response_bytes} bytes"
                    )
                return body
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 503} or attempt >= self.max_retries:
                    raise ArchiveSourceError(
                        f"archive source returned HTTP {exc.code} for {safe_url}"
                    ) from exc
                delay = _retry_after_seconds(exc.headers.get("Retry-After"))
                self._sleep(delay if delay is not None else min(2**attempt, 30))
            except urllib.error.URLError as exc:
                if attempt >= self.max_retries:
                    raise ArchiveSourceError(f"could not fetch {safe_url}: {exc.reason}") from exc
                self._sleep(min(2**attempt, 30))
            except UrlPolicyError:
                raise
        raise ArchiveSourceError(f"could not fetch {safe_url}")

    def get_text(self, url: str, source_host: str | None = None) -> str:
        """Fetch UTF-8 text, accepting a UTF-8 BOM."""
        try:
            return self.get_bytes(url, source_host=source_host).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArchiveSourceError(f"archive response from {url} was not UTF-8") from exc

    def _pace(self) -> None:
        wait = self.min_delay_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _sleep(seconds: float) -> None:
        time.sleep(max(0.0, min(seconds, 120.0)))


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
