"""CLI commands."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import click

from pdfscrape.archive.registry import SourceRegistry, SourceRegistryError
from pdfscrape.archive.site import (
    DEFAULT_SITE_TITLE,
    CatalogValidationError,
    StaticSiteBuilder,
    load_catalog_records,
    sanitize_record,
    validate_catalog,
)
from pdfscrape.chat import Orchestrator, resolve_providers
from pdfscrape.config import Config
from pdfscrape.providers import all_providers, provider_names


def _echo_result(result, verbose: bool = False) -> None:
    if result.ok:
        click.echo(f"\n=== {result.provider} ===")
        if result.model:
            click.echo(f"[model: {result.model}]", err=True)
        click.echo(result.output)
    else:
        click.echo(f"\n=== {result.provider} FAILED ===", err=True)
        click.echo(result.error, err=True)
    if verbose and result.raw:
        click.echo("\n--- raw ---", err=True)
        click.echo(result.raw[:4000], err=True)


@click.command()
def init():
    """Show the current provider setup and login state."""
    config = Config()
    click.echo("pdfscrape - provider status\n")
    click.echo(f"config: {config.path}")

    for provider in all_providers():
        try:
            status = provider.auth()
        except Exception as exc:  # noqa: BLE001
            click.echo(f"  {provider.name:<12} ERROR  {exc}", err=True)
            continue

        mark = "ok" if status.logged_in else "no"
        click.echo(f"  {provider.name:<12} {mark:<4} [{status.method or '-'}] {status.detail}")
        if not status.logged_in and status.login_hint:
            click.echo(f"  {'':<12} -> {status.login_hint}", err=True)


@click.command()
@click.argument("query", required=False)
@click.option("--provider", "-p", default=None,
              help="Provider name, comma separated list, or 'auto'.")
@click.option("--model", "-m", default=None, help="Override the model.")
@click.option("--timeout", default=None, type=int, help="Per-provider timeout in seconds.")
@click.option("--cwd", default=None, help="Working directory for the providers.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Include raw provider output.")
def chat(query, provider, model, timeout, cwd, as_json, verbose):
    """Send a prompt to one or more providers."""
    if not query:
        query = click.prompt("Prompt")
    if not query:
        click.echo("Empty prompt.", err=True)
        raise SystemExit(1)

    config = Config()
    names = resolve_providers(provider or config.get("chat.default_provider", "auto"))
    orchestrator = Orchestrator(cwd=cwd)
    timeout = timeout or config.get("chat.timeout", 600)

    if names == ["auto"]:
        results = orchestrator.auto(query, model=model, timeout=timeout)
    elif len(names) == 1:
        chosen = names[0]
        try:
            results = [orchestrator.single_with_config(chosen, query, model=model,
                                                      timeout=timeout)]
        except Exception as exc:  # noqa: BLE001
            click.echo(f"error: {exc}", err=True)
            raise SystemExit(1) from exc
    else:
        results = orchestrator.many(names, query, model=model, timeout=timeout)

    if as_json:
        payload = [
            {
                "provider": r.provider,
                "ok": r.ok,
                "model": r.model,
                "output": r.output,
                "error": r.error,
            }
            for r in results
        ]
        click.echo(json.dumps(payload, indent=2))
    else:
        for result in results:
            _echo_result(result, verbose)


@click.command()
def providers():
    """List the available providers."""
    for name in provider_names():
        click.echo(name)


@click.command()
@click.option("--provider", "-p", default=None, help="Start on one provider.")
@click.option("--question", "-q", default=None, help="Ask one question and exit.")
def terminal(provider, question):
    """Open the interactive terminal chat."""
    from pdfscrape.terminal import run_terminal

    raise SystemExit(run_terminal(provider=provider, question=question))


@click.command()
@click.option("--provider", "-p", default=None, help="Provider to sign in.")
@click.option("--all", "all_providers_flag", is_flag=True, help="Every provider.")
def login(provider, all_providers_flag):
    """Print the login command for a provider."""
    hints = {
        "codex": "codex login",
        "claude": "claude login",
        "antigravity": "open the Antigravity IDE and sign in with Google",
        "gemini": "migrate to Antigravity: https://antigravity.google",
        "copilot": "copilot login",
        "gitlab": "glab auth login",
        "ollama": "ollama serve",
    }

    if all_providers_flag or not provider:
        for name in provider_names():
            click.echo(f"  {name:<12} {hints.get(name, '')}")
        return

    for name in [n.strip() for n in provider.split(",") if n.strip()]:
        click.echo(hints.get(name, f"unknown provider: {name}"))


@click.group()
def archive():
    """Harvest, validate, and publish the Romanian historical PDF archive."""


def _enrich_records_with_ai(records: list[dict], provider: str) -> list[dict]:
    """Use an already-signed-in provider via Orchestrator to summarize records."""
    names = resolve_providers(provider)
    orchestrator = Orchestrator()
    for rec in records:
        if rec.get("summary"):
            continue
        snippet = rec.get("excerpt") or ""
        prompt = (
            "In 1-2 neutral archival sentences in English, summarize this historical "
            f"Romanian document title ({rec.get('year') or 'n.d.'}): {rec['title']}"
        )
        if snippet:
            prompt += f"\nFront-matter excerpt: {snippet[:600]}"
        if names == ["auto"]:
            results = orchestrator.auto(prompt, timeout=120)
        elif len(names) == 1:
            results = [orchestrator.single_with_config(names[0], prompt, timeout=120)]
        else:
            results = orchestrator.many(names, prompt, timeout=120)
        for res in results:
            if res.ok and res.output.strip():
                rec["summary"] = res.output.strip()
                break
    return records


@archive.command()
@click.option(
    "--sources",
    "-s",
    "sources_path",
    default="config/sources.yaml",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to sources YAML configuration.",
)
@click.option("--source", "source_filter", default=None, help="Harvest only one source id.")
@click.option("--limit", default=50, show_default=True, type=int, help="Max records per source.")
@click.option(
    "--output",
    "-o",
    "output_path",
    default="build/catalog.jsonl",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output JSONL catalog path.",
)
@click.option("--enrich/--no-enrich", default=False, help="Enrich summaries via signed-in AI.")
@click.option(
    "--provider", "-p", default="auto", show_default=True, help="AI provider for --enrich."
)
def harvest(sources_path, source_filter, limit, output_path, enrich, provider):
    """Harvest records from open-access repositories into a JSONL catalog."""
    try:
        registry = SourceRegistry(sources_path if sources_path.exists() else None)
    except SourceRegistryError as exc:
        raise click.ClickException(str(exc)) from exc

    enabled = registry.list_sources(enabled_only=True)
    if source_filter:
        if source_filter not in registry.sources:
            raise click.ClickException(f"Unknown archive source: {source_filter}")
        target_ids = [source_filter]
    else:
        target_ids = list(enabled)

    harvested: list[dict] = []
    for src_id in target_ids:
        try:
            adapter = registry.create_adapter(src_id)
        except SourceRegistryError as exc:
            raise click.ClickException(str(exc)) from exc
        if not hasattr(adapter, "harvest"):
            continue
        for raw in adapter.harvest(max_records=limit):
            item = dataclasses.asdict(raw) if dataclasses.is_dataclass(raw) else dict(raw)
            harvested.append(sanitize_record(item))

    if enrich and harvested:
        harvested = _enrich_records_with_ai(harvested, provider=provider)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for rec in harvested:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    click.echo(f"Harvested {len(harvested)} records to {output_path}")


@archive.command()
@click.option(
    "--input",
    "-i",
    "input_path",
    default="build/catalog.jsonl",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Catalog JSONL or JSON file to validate.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON report.")
def validate(input_path, as_json):
    """Validate every record against the public-HTTPS and Copilot URL policy."""
    try:
        records = load_catalog_records(input_path)
    except (FileNotFoundError, ValueError) as exc:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from exc

    report = validate_catalog(records)
    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2))
    else:
        click.echo(
            f"Validated {report.total} records: {report.valid} valid, {report.invalid} invalid"
        )
        for issue in report.issues:
            click.echo(
                f"  - [{issue.reason}] {issue.record_id}.{issue.field}: {issue.detail}",
                err=True,
            )

    if not report.ok:
        raise SystemExit(1)


@archive.command(name="build-site")
@click.option(
    "--input",
    "-i",
    "input_path",
    default="build/catalog.jsonl",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Catalog JSONL or JSON file.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    default="dist/archive",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for the static site.",
)
@click.option("--title", default=DEFAULT_SITE_TITLE, show_default=True, help="Catalog page title.")
@click.option(
    "--allow-invalid",
    is_flag=True,
    help="Skip records that fail URL validation instead of aborting.",
)
def build_site(input_path, output_dir, title, allow_invalid):
    """Build the static archival search UI and catalog.json."""
    try:
        records = load_catalog_records(input_path)
        result = StaticSiteBuilder().build(
            records,
            output_dir,
            title=title,
            strict=not allow_invalid,
        )
    except (FileNotFoundError, ValueError) as exc:
        if isinstance(exc, CatalogValidationError):
            for issue in exc.report.issues:
                click.echo(
                    f"  - [{issue.reason}] {issue.record_id}.{issue.field}: {issue.detail}",
                    err=True,
                )
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from exc

    summary = f"Built static archive site ({result.record_count} records) in {result.output_dir}"
    if result.skipped_count:
        summary += f" (skipped {result.skipped_count} invalid)"
    click.echo(summary)
