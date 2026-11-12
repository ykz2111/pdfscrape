import json
from urllib.parse import parse_qs, urlsplit

import pytest

from pdfscrape.archive.internet_archive import InternetArchiveAdapter


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get_bytes(self, url, source_host=None):
        self.urls.append(url)
        return json.dumps(self.responses.pop(0)).encode()


def test_harvest_searches_open_api_and_normalizes_metadata_and_files():
    search = {"response": {"numFound": 1, "docs": [{"identifier": "carte-1890"}]}}
    metadata = {
        "metadata": {
            "title": ["Cronica veche"],
            "creator": ["Ion Pop", "Maria Ionescu"],
            "date": "1890",
            "language": "Romanian",
            "rights": "Public Domain",
        },
        "files": [
            {"name": "carte.pdf", "format": "PDF", "sha1": "pdf-checksum"},
            {"name": "carte.txt", "format": "Text", "md5": "text-checksum"},
        ],
    }
    client = FakeHttp([search, metadata])
    adapter = InternetArchiveAdapter(http_client=client)

    records = adapter.harvest(max_records=5)

    assert len(records) == 1
    record = records[0]
    assert record.id == "carte-1890"
    assert record.title == "Cronica veche"
    assert record.creators == ["Ion Pop", "Maria Ionescu"]
    assert record.year == "1890"
    assert record.language == "Romanian"
    assert record.rights == "Public Domain"
    assert record.landing_url == "https://archive.org/details/carte-1890"
    assert record.pdf_url == "https://archive.org/download/carte-1890/carte.pdf"
    assert record.text_url == "https://archive.org/download/carte-1890/carte.txt"
    assert record.checksum == "pdf-checksum"
    assert parse_qs(urlsplit(client.urls[0]).query)["q"] == ["language:rum AND mediatype:texts"]


def test_rejects_unsafe_identifiers_before_request():
    adapter = InternetArchiveAdapter(http_client=FakeHttp([]))
    with pytest.raises(ValueError, match="unsupported characters"):
        adapter.get_record("../private")
