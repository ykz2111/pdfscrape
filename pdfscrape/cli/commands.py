"""CLI commands."""

from __future__ import annotations

import json

import click

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
