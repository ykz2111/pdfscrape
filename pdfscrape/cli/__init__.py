"""CLI entrypoint."""

from __future__ import annotations

import click

from pdfscrape.cli.commands import chat, init, login, providers, terminal


@click.group()
@click.version_option(package_name="pdfscrape")
def main() -> None:
    """pdfscrape - one CLI for every AI provider you are signed in to.

    Every provider is reached through its own CLI, which holds the OAuth
    session. pdfscrape never stores or sends an API key.
    """
    pass


main.add_command(init)
main.add_command(chat)
main.add_command(login)
main.add_command(providers)
main.add_command(terminal)


if __name__ == "__main__":
    main()
