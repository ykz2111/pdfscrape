import urllib.error
from email.message import Message

import pytest

from pdfscrape.archive.http import ArchiveHttpClient, _retry_after_seconds
from pdfscrape.archive.url_policy import UrlPolicyError


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_http_client_retries_503_and_returns_body(monkeypatch):
    headers = Message()
    headers["Retry-After"] = "0"
    error = urllib.error.HTTPError("https://archive.org/", 503, "Busy", headers, None)
    opener = FakeOpener([error, FakeResponse(b"ok")])
    monkeypatch.setattr(ArchiveHttpClient, "_sleep", staticmethod(lambda _: None))
    client = ArchiveHttpClient(min_delay_seconds=0, max_retries=1, opener=opener)

    assert client.get_bytes("https://archive.org/") == b"ok"
    assert len(opener.requests) == 2
    assert opener.requests[0].get_header("User-agent").startswith("pdfscrape-archive/")


def test_http_client_rejects_unsafe_url_before_request():
    opener = FakeOpener([])
    client = ArchiveHttpClient(min_delay_seconds=0, opener=opener)
    with pytest.raises(UrlPolicyError):
        client.get_bytes("http://localhost/secret")
    assert opener.requests == []


def test_retry_after_accepts_seconds_and_http_date():
    assert _retry_after_seconds("5") == 5.0
    assert _retry_after_seconds("not a date") is None
