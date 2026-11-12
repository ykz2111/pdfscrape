# Romanian historical archive catalog: plan

Status: accepted. Work is staged as four phases, each on its own branch stacked on this one
(`main` → `plan` → `phase-N`).

## Goal

Harvest unindexed Romanian historical PDFs (metadata and front-matter text), enrich them
through the AI providers `pdfscrape` is already signed in to, and publish a static, searchable
catalog on GitHub or GitLab Pages. Choosing a document in Safari hands off to Copilot with a
guaranteed public `https://` URL, never `localhost`.

## Corrections to earlier drafts

| Issue | Conflict | Correction |
|---|---|---|
| `EUROPEANA_API_KEY` | `AGENTS.md` forbids API-key handling and pasted secrets. | Harvest only open, unauthenticated protocols: OAI-PMH, Internet Archive public JSON APIs, Gallica OAI/IIIF and public institutional catalogs. AI enrichment goes through the existing `Orchestrator`, which reuses signed-in CLI sessions. |
| Separate `archive_index` package on Python 3.12 | This repo is `pdfscrape`, `requires-python >= 3.9`, `click`, `pyyaml`, stdlib `urllib`. | Build it as a bounded submodule, `pdfscrape/archive/`, Python 3.9 compatible and stdlib first, exposed as `pdfscrape archive ...` subcommands. |
| DSpace `localhost` and raw-IP poisoning | `dspace.bcucluj.ro` emits `<repositoryIdentifier>localhost</repositoryIdentifier>` and `http://` bitstream URLs. `dspace.bcu-iasi.ro` emits `193.231.13.161`. | A `UrlPolicy` normalizer at the ingestion boundary rewrites known hosts to canonical public `https://` hosts and rejects `localhost`, `127.0.0.1`, private RFC1918 ranges and `file://`. |

## Architecture decision

**Pipes-and-filters ingestion, one adapter per source, static Pagefind-style catalog,
implemented inside `pdfscrape/archive/`.**

1. **Source adapters** (`OaiPmhAdapter`, `InternetArchiveAdapter`, `GallicaIiifAdapter`) pull
   raw records over open protocols only. No API keys.
2. **URL guard** (`UrlPolicy`) canonicalizes URLs to public `https://` and blocks loopback and
   private addresses at ingestion and again at export.
3. **AI enrichment** uses `pdfscrape.chat.Orchestrator` to summarize and normalize archaic or
   Cyrillic Romanian titles through already-authenticated providers.
4. **Static catalog builder** writes `catalog.json` and a zero-backend HTML/CSS/JS search UI.

Consequences:

- No API keys or `.env` secrets anywhere in the stack.
- Python 3.9+ with stdlib `urllib.request` and `xml.etree.ElementTree`; no heavy mandatory
  dependencies.
- Build artifacts (`catalog.json`, static HTML) are deployed to Pages and never committed as
  large binary blobs.

Rejected alternatives:

- Committing `archive.sqlite` to Git: binary diff bloat against the 1 to 2 GB host limits.
- The Europeana Search REST API: its `wskey` violates the no-API-key rule.

## Component design

### URL guard and Copilot router

`pdfscrape/archive/url_policy.py`

- `canonicalize_public_url(url, source_host=None) -> str` raises `UrlPolicyError` on
  `localhost`, `127.0.0.1`, `0.0.0.0`, RFC1918 ranges, `file://` or non-HTTPS.
- `build_copilot_url(title, public_url, year=None) -> str` returns
  `https://github.com/copilot?prompt=...`.

### Source registry and adapters

- `config/sources.yaml`: declarative open-access sources (`bcucluj`, `internet_archive`,
  `gallica`; `bcu_iasi` disabled until its OAI endpoint returns records).
- `pdfscrape/archive/models.py`: `ArchiveRecord` dataclass (`id`, `source_id`, `title`,
  `creators`, `year`, `period`, `language`, `rights`, `landing_url`, `pdf_url`, `text_url`,
  `checksum`, `copilot_url`).
- `pdfscrape/archive/oai.py`: stdlib OAI-PMH harvester for `xoai` and `oai_dc`. It extracts PDF
  and text bitstreams from DSpace bundles and upgrades `http://dspace.bcucluj.ro` to `https://`.
- `pdfscrape/archive/internet_archive.py`: queries `archive.org/advancedsearch.php`
  (`language:rum AND mediatype:texts`) and `archive.org/metadata/{id}`.

### Static site and design tokens

- `pdfscrape/archive/site.py` renders the search interface and writes `catalog.json`.
- `pdfscrape/archive/assets/tokens.css` defines the tokens on an 8pt grid: warm parchment
  canvas `#FDFBF7`, surface `#FFFFFF`, text `#0F172A`, muted text `#475569`, accent terracotta
  `#9A3412`, border `#E2E8F0`. Editorial serif headings, clean UI body, tabular numerals.
- Accessibility: SVG icons only, visible `:focus-visible` rings, 44 by 44 px touch targets,
  `prefers-reduced-motion` support. Client-side JS refuses to open any Safari or Copilot link
  unless `url.protocol === "https:"` and the host is not loopback.

### CLI and DevOps

- `pdfscrape/cli/commands.py`: an `archive` group with `harvest`, `validate` and `build-site`.
- `pyproject.toml`: register `pdfscrape.archive` in `packages`.
- `.devcontainer/`: Python, Node, Tesseract (`ron`, `eng`) and Poppler.
- `.github/workflows/archive-pages.yml`: weekly cron and `workflow_dispatch`; harvest,
  validate (fail on any `localhost` leak), deploy to Pages.
- Tests: `tests/test_archive_url_policy.py`, `tests/test_archive_oai.py`.

## Data flow

```text
config/sources.yaml
        |
        v
Source adapter (BCU Cluj OAI / Internet Archive JSON / Gallica OAI)
        |  raw XML or JSON, may contain "oai:localhost:..." or "http://..."
        v
UrlPolicy.canonicalize_public_url()   rejects localhost, 127.0.0.1, private IPs;
        |                             upgrades known repository http:// to https://
        v
ArchiveRecord + build_copilot_url()   https://github.com/copilot?prompt=...
        |
        +--> optional pdfscrape Orchestrator enrichment (OAuth CLIs, no keys)
        v
build/catalog.jsonl --> pdfscrape archive validate (CI hard gate)
        |
        v
StaticSiteBuilder --> dist/archive/{index.html, tokens.css, app.js, catalog.json}
```

## Security and quality checklist

- **SSRF and loopback:** `ipaddress` checks block loopback, link-local and private networks, and
  `localhost` names, before any URL is fetched or written to the catalog.
- **XML safety:** reject `<!DOCTYPE` and `<!ENTITY` in untrusted OAI-PMH responses (XXE and
  entity-expansion attacks).
- **No secrets:** no API keys, `.env` files or credentials in `sources.yaml` or CI.
- **Polite crawling:** one request at a time per host, `min_delay_seconds: 1.0`, a descriptive
  `User-Agent`, and `Retry-After` handling on HTTP 429 and 503.

## Build sequence

| Phase | Branch | Scope |
|---|---|---|
| 1 | `phase-1` | URL guard and Copilot router (`url_policy.py`, tests) |
| 2 | `phase-2` | Models, source adapters, `config/sources.yaml`, tests |
| 3 | `phase-3` | Static archival UI, `archive` CLI commands |
| 4 | `phase-4` | DevContainer and CI/Pages pipeline |

Each phase branches from `plan` (or the previous phase) and is reviewed on its own.
