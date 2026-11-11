"""CLI entrypoint and command routing."""

import click
from pdfscrape.cli.commands import chat, init, config


@click.group()
@click.version_option()
def main():
    """pdfscrape - Orchestrate multiple AI models and chat platforms."""
    pass


main.add_command(init)
main.add_command(chat)
main.add_command(config)


if __name__ == "__main__":
    main()
