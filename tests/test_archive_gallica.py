import pytest

from pdfscrape.archive.gallica import GallicaIiifAdapter
from pdfscrape.archive.url_policy import UrlPolicyError


def test_extracts_metadata_and_public_resources_from_iiif_manifest():
    adapter = GallicaIiifAdapter()
    manifest = {
        "label": {"ro": ["Carte din Gallica"]},
        "metadata": [
            {"label": "Creator", "value": "Ion Pop"},
            {"label": "Date", "value": "1892"},
            {"label": "Language", "value": "Romanian"},
            {"label": "Rights", "value": "Public domain"},
            {"label": "Identifier", "value": "ark:/12148/bpt6k123"},
        ],
        "seeAlso": [
            {"id": "https://gallica.bnf.fr/download/bpt6k123.pdf", "format": "application/pdf"},
            {"id": "https://gallica.bnf.fr/ocr/bpt6k123.txt", "format": "text/plain"},
        ],
    }

    record = adapter.record_from_manifest(
        manifest, "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k123/manifest.json"
    )

    assert record.id == "ark:/12148/bpt6k123"
    assert record.title == "Carte din Gallica"
    assert record.creators == ["Ion Pop"]
    assert record.year == "1892"
    assert record.language == "Romanian"
    assert record.rights == "Public domain"
    assert record.pdf_url == "https://gallica.bnf.fr/download/bpt6k123.pdf"
    assert record.text_url == "https://gallica.bnf.fr/ocr/bpt6k123.txt"
    assert record.landing_url.startswith("https://gallica.bnf.fr/iiif/")
    assert record.copilot_url.startswith("https://github.com/copilot?")


def test_rejects_private_iiif_resource_url():
    adapter = GallicaIiifAdapter()
    with pytest.raises(UrlPolicyError):
        adapter.record_from_manifest(
            {"rendering": [{"id": "http://127.0.0.1/document.pdf", "format": "application/pdf"}]},
            "https://gallica.bnf.fr/iiif/manifest.json",
        )
