"""Tests for the static archival UI builder and archive CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from click.testing import CliRunner

from pdfscrape.archive.site import (
    ASSETS_DIR,
    CatalogValidationError,
    StaticSiteBuilder,
    load_catalog_records,
    sanitize_record,
    validate_catalog,
)
from pdfscrape.cli import main


def _sample_records():
    return [
        {
            "id": "bcucluj:12345",
            "source_id": "bcucluj",
            "source_name": "BCU Cluj Digital Library",
            "title": "Gazeta Transilvaniei — Anul XLII (1879)",
            "creators": ["George Barițiu"],
            "year": "1879",
            "period": "19th Century",
            "language": "Romanian",
            "rights": "Public Domain",
            "landing_url": "http://dspace.bcucluj.ro/handle/123456789/101",
            "pdf_url": "http://dspace.bcucluj.ro/bitstream/123456789/101/1/gazeta.pdf",
            "text_url": "http://dspace.bcucluj.ro/bitstream/123456789/101/2/gazeta.pdf.txt",
            "checksum": "sha256:abc123",
            "summary": "Issue from 1879 covering cultural and parliamentary news in Transylvania.",
            "excerpt": "Brașov, 14 Ianuarie 1879 — Foaia politică și literară.",
        },
        {
            "id": "ia:romanian-chronicle",
            "source_id": "internet_archive",
            "source_name": "Internet Archive",
            "title": "Letopisețul Țării Moldovei",
            "creators": ["Grigore Ureche", "Miron Costin"],
            "year": "1916",
            "period": "Early 20th Century",
            "language": "Romanian",
            "rights": "Public Domain",
            "landing_url": "https://archive.org/details/letopisetul-1916",
            "pdf_url": "http://ia800100.us.archive.org/1/items/letopisetul-1916/letopisetul.pdf",
        },
    ]


def test_sanitize_record_upgrades_known_hosts_and_builds_copilot_url():
    rec = sanitize_record(_sample_records()[0])
    assert rec["landing_url"] == "https://dspace.bcucluj.ro/handle/123456789/101"
    assert rec["pdf_url"] == "https://dspace.bcucluj.ro/bitstream/123456789/101/1/gazeta.pdf"
    assert rec["text_url"] == "https://dspace.bcucluj.ro/bitstream/123456789/101/2/gazeta.pdf.txt"

    parts = urlsplit(rec["copilot_url"])
    assert parts.scheme == "https"
    assert parts.netloc == "github.com"
    assert parts.path == "/copilot"
    prompt = parse_qs(parts.query)["prompt"][0]
    assert "https://dspace.bcucluj.ro/bitstream/123456789/101/1/gazeta.pdf" in prompt


def test_sanitize_record_rewrites_leaked_iasi_ip():
    rec = sanitize_record(
        {
            "id": "iasi:9",
            "source_id": "bcu_iasi",
            "title": "Archival Monograph",
            "landing_url": "http://193.231.13.161/handle/123456789/9",
        }
    )
    assert rec["landing_url"] == "https://dspace.bcu-iasi.ro/handle/123456789/9"


@pytest.mark.parametrize(
    "bad_url, expected_reason",
    [
        ("http://localhost:8080/bitstream/1/doc.pdf", "port"),
        ("https://localhost/bitstream/1/doc.pdf", "loopback"),
        ("https://127.0.0.1/handle/1", "loopback"),
        ("https://192.168.1.50/handle/1", "private_ip"),
        ("file:///etc/passwd", "scheme"),
        ("http://unknown-host.example/doc.pdf", "insecure"),
    ],
)
def test_validate_catalog_rejects_unsafe_urls(bad_url, expected_reason):
    records = [
        {
            "id": "bad:1",
            "source_id": "bcucluj",
            "title": "Poisoned Record",
            "landing_url": "https://dspace.bcucluj.ro/handle/1",
            "pdf_url": bad_url,
        }
    ]
    report = validate_catalog(records)
    assert not report.ok
    assert report.invalid == 1
    assert report.issues[0].reason == expected_reason


def test_validate_catalog_rejects_poisoned_copilot_url():
    records = [
        {
            "id": "bad:copilot",
            "source_id": "bcucluj",
            "title": "Tampered Copilot",
            "landing_url": "https://dspace.bcucluj.ro/handle/1",
            "copilot_url": "https://github.com/copilot?prompt=Summarize%20Source:%20http://localhost/x.pdf",
        }
    ]
    report = validate_catalog(records)
    assert not report.ok
    assert report.issues[0].field == "copilot_url"


def test_static_site_builder_outputs_assets_and_catalog(tmp_path: Path):
    out_dir = tmp_path / "site"
    result = StaticSiteBuilder().build(
        _sample_records(),
        out_dir,
        title='Arhiva Română <Test>',
    )

    assert result.record_count == 2
    assert result.skipped_count == 0
    expected_files = (
        "catalog.json",
        "index.html",
        "tokens.css",
        "styles.css",
        "app.js",
        ".nojekyll",
    )
    for expected in expected_files:
        assert (out_dir / expected).is_file()

    catalog = json.loads((out_dir / "catalog.json").read_text(encoding="utf-8"))
    assert isinstance(catalog, list)
    assert len(catalog) == 2
    for rec in catalog:
        assert rec["landing_url"].startswith("https://")
        assert rec["copilot_url"].startswith("https://github.com/copilot?prompt=")

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "Arhiva Română &lt;Test&gt;" in html_text
    assert "<Test>" not in html_text


def test_static_site_builder_strict_and_non_strict(tmp_path: Path):
    records = _sample_records() + [
        {
            "id": "bad:loopback",
            "source_id": "bcucluj",
            "title": "Bad Record",
            "landing_url": "http://localhost/handle/1",
        }
    ]

    with pytest.raises(CatalogValidationError):
        StaticSiteBuilder().build(records, tmp_path / "strict", strict=True)

    res = StaticSiteBuilder().build(records, tmp_path / "lenient", strict=False)
    assert res.record_count == 2
    assert res.skipped_count == 1


def test_load_catalog_records_supports_jsonl_and_json(tmp_path: Path):
    jsonl_path = tmp_path / "catalog.jsonl"
    jsonl_path.write_text(
        "\n".join(json.dumps(r) for r in _sample_records()) + "\n",
        encoding="utf-8",
    )
    assert len(load_catalog_records(jsonl_path)) == 2

    json_path = tmp_path / "catalog.json"
    json_path.write_text(json.dumps({"records": _sample_records()}), encoding="utf-8")
    assert len(load_catalog_records(json_path)) == 2


def test_design_tokens_and_accessibility_contracts():
    tokens_css = (ASSETS_DIR / "tokens.css").read_text(encoding="utf-8")
    styles_css = (ASSETS_DIR / "styles.css").read_text(encoding="utf-8")
    app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
    index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")

    for hex_token in ("#FDFBF7", "#FFFFFF", "#0F172A", "#475569", "#9A3412", "#E2E8F0"):
        assert hex_token in tokens_css
    assert "prefers-reduced-motion" in tokens_css
    assert "--touch-min: 44px" in tokens_css
    assert ":focus-visible" in styles_css
    assert "isSafePublicHttpsUrl" in app_js
    assert 'parsed.protocol !== "https:"' in app_js
    assert "<svg" in index_html


def test_cli_archive_validate_and_build_site(tmp_path: Path):
    runner = CliRunner()
    jsonl_path = tmp_path / "catalog.jsonl"
    jsonl_path.write_text(
        "\n".join(json.dumps(r) for r in _sample_records()) + "\n",
        encoding="utf-8",
    )

    val_res = runner.invoke(main, ["archive", "validate", "-i", str(jsonl_path), "--json"])
    assert val_res.exit_code == 0, val_res.output
    payload = json.loads(val_res.output)
    assert payload["ok"] is True
    assert payload["total"] == 2

    site_dir = tmp_path / "dist"
    build_res = runner.invoke(
        main,
        ["archive", "build-site", "-i", str(jsonl_path), "-o", str(site_dir)],
    )
    assert build_res.exit_code == 0, build_res.output
    assert (site_dir / "index.html").is_file()
    assert (site_dir / "catalog.json").is_file()


def test_cli_archive_validate_fails_on_localhost_leak(tmp_path: Path):
    runner = CliRunner()
    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_text(
        json.dumps(
            {
                "id": "bad:1",
                "source_id": "bcucluj",
                "title": "Leaked localhost",
                "landing_url": "http://localhost/handle/1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    res = runner.invoke(main, ["archive", "validate", "-i", str(bad_jsonl)])
    assert res.exit_code == 1
    assert "loopback" in res.output


def test_cli_archive_harvest_with_registry_adapter(tmp_path: Path, monkeypatch):
    from pdfscrape.archive.oai import OaiPmhAdapter

    runner = CliRunner()
    sources_yaml = tmp_path / "sources.yaml"
    sources_yaml.write_text(
        "sources:\n"
        "  bcucluj:\n"
        "    adapter: oai\n"
        "    enabled: true\n"
        "    endpoint: https://dspace.bcucluj.ro/server/oai/request\n"
        "    metadata_prefix: xoai\n"
        "    source_host: dspace.bcucluj.ro\n",
        encoding="utf-8",
    )
    out_jsonl = tmp_path / "harvested.jsonl"

    monkeypatch.setattr(
        OaiPmhAdapter,
        "harvest",
        lambda self, max_records=50: [_sample_records()[0]],
    )

    res = runner.invoke(
        main,
        ["archive", "harvest", "-s", str(sources_yaml), "-o", str(out_jsonl), "--limit", "5"],
    )
    assert res.exit_code == 0, res.output
    loaded = load_catalog_records(out_jsonl)
    assert len(loaded) == 1
    assert loaded[0]["landing_url"] == "https://dspace.bcucluj.ro/handle/123456789/101"
