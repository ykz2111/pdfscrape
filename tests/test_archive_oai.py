from urllib.parse import parse_qs, urlsplit

import pytest

from pdfscrape.archive.http import ArchiveSourceError
from pdfscrape.archive.oai import OaiPmhAdapter, _parse_xml

FIRST_PAGE = b"""<?xml version="1.0"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header><identifier>oai:dspace.bcucluj.ro:123</identifier></header>
      <metadata>
        <dim:dim xmlns:dim="http://www.dspace.org/xmlns/dspace/dim">
          <dim:field mdschema="dc" element="title" qualifier="none">
            Cronica romaneasca veche
          </dim:field>
          <dim:field mdschema="dc" element="creator" qualifier="none">Ion Pop</dim:field>
          <dim:field mdschema="dc" element="date" qualifier="issued">1890</dim:field>
          <dim:field mdschema="dc" element="language" qualifier="iso">rum</dim:field>
          <dim:field mdschema="dc" element="rights" qualifier="none">Public domain</dim:field>
          <dim:field mdschema="dc" element="identifier" qualifier="uri">http://dspace.bcucluj.ro/handle/123</dim:field>
          <dim:field mdschema="dc" element="identifier" qualifier="uri">http://dspace.bcucluj.ro/bitstream/123/book.pdf</dim:field>
          <dim:field mdschema="dc" element="identifier" qualifier="uri">http://dspace.bcucluj.ro/bitstream/123/book.txt</dim:field>
          <dim:field mdschema="internal" element="checksum" qualifier="none">abc123</dim:field>
        </dim:dim>
      </metadata>
    </record>
    <record>
      <header status="deleted"><identifier>oai:dspace.bcucluj.ro:gone</identifier></header>
    </record>
    <resumptionToken>next-page</resumptionToken>
  </ListRecords>
</OAI-PMH>"""

SECOND_PAGE = b"""<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record><header><identifier>oai:dspace.bcucluj.ro:456</identifier></header>
      <metadata><oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/">
        <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Second record</dc:title>
      </oai_dc:dc></metadata>
    </record>
    <resumptionToken/>
  </ListRecords>
</OAI-PMH>"""


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get_bytes(self, url, source_host=None):
        self.urls.append(url)
        return self.responses.pop(0)


def test_harvest_parses_dspace_metadata_and_resumption_tokens():
    client = FakeHttp([FIRST_PAGE, SECOND_PAGE])
    adapter = OaiPmhAdapter(
        "https://dspace.bcucluj.ro/server/oai/request",
        "bcucluj",
        metadata_prefix="xoai",
        source_host="dspace.bcucluj.ro",
        http_client=client,
    )

    records = adapter.harvest()

    assert len(records) == 2
    record = records[0]
    assert record.id == "oai:dspace.bcucluj.ro:123"
    assert record.title == "Cronica romaneasca veche"
    assert record.creators == ["Ion Pop"]
    assert record.year == "1890"
    assert record.language == "rum"
    assert record.rights == "Public domain"
    assert record.landing_url == "https://dspace.bcucluj.ro/handle/123"
    assert record.pdf_url == "https://dspace.bcucluj.ro/bitstream/123/book.pdf"
    assert record.text_url == "https://dspace.bcucluj.ro/bitstream/123/book.txt"
    assert record.checksum == "abc123"
    assert record.copilot_url.startswith("https://github.com/copilot?")
    assert parse_qs(urlsplit(client.urls[0]).query)["metadataPrefix"] == ["xoai"]
    assert parse_qs(urlsplit(client.urls[1]).query)["resumptionToken"] == ["next-page"]


def test_harvest_obeys_max_records():
    client = FakeHttp([FIRST_PAGE])
    adapter = OaiPmhAdapter(
        "https://dspace.bcucluj.ro/server/oai/request", "bcucluj", http_client=client
    )
    records = adapter.harvest(max_records=1)
    assert len(records) == 1


def test_harvest_rejects_unsafe_metadata_urls():
    payload = FIRST_PAGE.replace(
        b"http://dspace.bcucluj.ro/handle/123", b"http://localhost/handle/123"
    )
    adapter = OaiPmhAdapter(
        "https://dspace.bcucluj.ro/server/oai/request",
        "bcucluj",
        http_client=FakeHttp([payload]),
    )
    with pytest.raises(ArchiveSourceError, match="unsafe document URL"):
        adapter.harvest()


def test_harvest_builds_dspace_bitstream_links_from_xoai_bundles():
    payload = b"""<OAI-PMH><ListRecords><record>
      <header><identifier>oai:dspace.bcucluj.ro:123</identifier></header>
      <metadata><metadata>
        <element name="dc"><element name="title"><element name="none">Scan</element></element>
          <element name="identifier"><element name="uri">https://dspace.bcucluj.ro/handle/12/34</element></element>
        </element>
        <element name="bundles"><element name="bundle"><element name="bitstreams">
          <element name="bitstream"><element name="name">scan.pdf</element>
            <element name="sequence_id">2</element><element name="checksum">pdf-hash</element>
          </element>
          <element name="bitstream"><element name="name">scan.txt</element>
            <element name="sequence_id">3</element>
          </element>
        </element></element></element>
      </metadata></metadata>
    </record></ListRecords></OAI-PMH>"""
    adapter = OaiPmhAdapter(
        "https://dspace.bcucluj.ro/server/oai/request",
        "bcucluj",
        metadata_prefix="xoai",
        source_host="dspace.bcucluj.ro",
        http_client=FakeHttp([payload]),
    )

    record = adapter.harvest()[0]

    assert record.title == "Scan"
    assert record.pdf_url == (
        "https://dspace.bcucluj.ro/bitstream/handle/12/34/scan.pdf?sequence=2&isAllowed=y"
    )
    assert record.text_url == (
        "https://dspace.bcucluj.ro/bitstream/handle/12/34/scan.txt?sequence=3&isAllowed=y"
    )
    assert record.checksum == "pdf-hash"


def test_xml_parser_rejects_dtd_and_entities():
    with pytest.raises(ArchiveSourceError, match="DTD or entity"):
        _parse_xml(b'<!DOCTYPE x [<!ENTITY secret "boom">]><x>&secret;</x>')


def test_no_records_match_is_an_empty_result():
    client = FakeHttp([b'<OAI-PMH><error code="noRecordsMatch">No records</error></OAI-PMH>'])
    adapter = OaiPmhAdapter(
        "https://dspace.bcucluj.ro/server/oai/request", "bcucluj", http_client=client
    )
    assert adapter.harvest() == []
