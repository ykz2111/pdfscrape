"""CLI commands."""

import click


@click.command()
def init():
    """Initialize pdfscrape configuration."""
    click.echo("🚀 Initializing pdfscrape...")
    click.echo("Configure providers: GitHub Copilot, Claude, Gemini, Ollama, GitLab Chat")
    # TODO: Interactive config setup


@click.command()
@click.argument("query")
@click.option("--provider", default="auto", help="AI provider to use")
@click.option("--gitlab-chat", is_flag=True, help="Use GitLab Chat for response")
def chat(query, provider, gitlab_chat):
    """Chat with AI orchestrator."""
    click.echo(f"💬 {query}")
    click.echo(f"Provider: {provider}")
    if gitlab_chat:
        click.echo("📤 Routing to GitLab Chat...")
    # TODO: Implement chat orchestration


@click.command()
def config():
    """Manage pdfscrape configuration."""
    click.echo("⚙️  Configuration management")
    # TODO: Config management UI
