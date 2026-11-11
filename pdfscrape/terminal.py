"""Interactive terminal chat for macOS Terminal and other TTYs.

This is the terminal-native counterpart to the OpenCode plugin: a REPL that
takes a prompt, sends it to the providers, and prints the answers with colour
and per-provider headers.

Colours are used as decoration only. Every status is also spelled out in
words, so the output stays readable when piped to a file or read by someone
who cannot see colour.
"""

from __future__ import annotations

import os
import sys

from pdfscrape.chat import Orchestrator
from pdfscrape.config import Config
from pdfscrape.providers import all_providers, provider_names

# ---------------------------------------------------------------- colour ----

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "grey": "\033[90m",
}


def colour_enabled(stream=None) -> bool:
    """Whether ANSI colour should be used.

    Honours NO_COLOR and TERM=dumb, and stays off when output is not a TTY.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    stream = stream or sys.stdout
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


class Style:
    """Applies ANSI codes, or nothing when colour is off."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def __call__(self, text: str, *names: str) -> str:
        if not self.enabled or not names:
            return text
        prefix = "".join(_ANSI.get(name, "") for name in names)
        return f"{prefix}{text}{_ANSI['reset']}"


# ----------------------------------------------------------------- REPL ----

BANNER = """pdfscrape terminal
Type a question and press enter. /help for commands, /quit to exit."""

HELP = """Commands
  /help              show this help
  /status            provider sign-in status
  /providers         list providers and their models
  /login [provider]  show how to sign in (or sign in now)
  /use <provider>    send to one provider (auto = every signed-in one)
  /model <provider> <model>
                     set the model for a provider
  /clear             clear the screen
  /history           show recent prompts
  /quit              exit

Anything else is sent to the providers as a prompt."""

# Commands that are handled in-process rather than sent to a provider.
COMMANDS = {
    "/help", "/status", "/providers", "/login",
    "/use", "/model", "/clear", "/history", "/quit", "/exit",
}

LOGIN_HINTS = {
    "codex": "codex login",
    "claude": "claude login",
    "antigravity": "open the Antigravity IDE and sign in with Google",
    "gemini": "migrate to Antigravity: https://antigravity.google",
    "copilot": "copilot login",
    "gitlab": "glab auth login",
    "ollama": "ollama serve",
}


class TerminalChat:
    """An interactive session over the pdfscrape providers."""

    def __init__(self, style: Style | None = None, cwd: str | None = None,
                 default_provider: str | None = None):
        self.style = style or Style(colour_enabled())
        self.config = Config()
        self.orchestrator = Orchestrator(cwd=cwd)
        self.cwd = cwd
        self.provider = (
            default_provider
            or self.config.get("chat.default_provider", "auto")
            or "auto"
        )
        self.history: list[str] = []
        self.running = True

    # -- output helpers ---------------------------------------------------

    def say(self, text: str = "") -> None:
        print(text)

    def error(self, text: str) -> None:
        print(self.style(text, "red"), file=sys.stderr)

    def header(self, provider: str, model: str = "") -> None:
        label = provider if not model else f"{provider}  {model}"
        print(self.style(f"\n▌ {label}", "bold", "cyan"))

    # -- commands ----------------------------------------------------------

    def cmd_help(self) -> None:
        self.say(HELP)

    def cmd_status(self) -> None:
        self.say(self.style("Provider sign-in status", "bold"))
        for provider in all_providers(cwd=self.cwd):
            try:
                status = provider.auth()
            except Exception as exc:  # noqa: BLE001
                self.say(f"  {provider.name:<12} {self.style('error', 'red')}  {exc}")
                continue

            if status.logged_in:
                mark = self.style("ok", "green")
                detail = self.style(status.detail, "grey")
            else:
                mark = self.style("not signed in", "yellow")
                detail = self.style(status.detail, "grey")
            self.say(f"  {provider.name:<12} {mark:<14} {detail}")

            if not status.logged_in and status.login_hint:
                self.say(f"  {'':<12} {self.style('-> ' + status.login_hint, 'yellow')}")

    def cmd_providers(self) -> None:
        self.say(self.style("Providers", "bold"))
        for provider in all_providers(cwd=self.cwd):
            models = []
            lister = getattr(provider, "available_models", None)
            if callable(lister):
                try:
                    models = lister()
                except Exception:  # noqa: BLE001
                    models = []

            configured = self.config.model_for(provider.name)
            shown = configured or "(default)"
            self.say(
                f"  {provider.name:<12} "
                f"{self.style('model: ' + str(shown), 'grey')}"
            )
            if models:
                listed = ", ".join(models[:8])
                self.say(f"  {'':<12} {self.style('available: ' + listed, 'grey')}")

    def cmd_login(self, arg: str) -> None:
        if not arg:
            self.say(self.style("Sign-in commands", "bold"))
            for name in provider_names():
                self.say(f"  {name:<12} {LOGIN_HINTS.get(name, '')}")
            self.say(self.style("\nUse /login <provider> to run one now.", "grey"))
            return

        name = arg.strip().lower()
        if name not in provider_names():
            self.error(f"Unknown provider: {name}")
            return

        hint = LOGIN_HINTS.get(name)
        self.say(self.style(f"Signing in: {name}", "bold"))
        self.say(f"  {hint}")
        self.say(self.style("  (run that command, then re-run /status)", "grey"))

    def cmd_use(self, arg: str) -> None:
        if not arg:
            self.say(f"Current provider: {self.style(self.provider, 'cyan')}")
            return
        name = arg.strip().lower()
        if name != "auto" and name not in provider_names():
            self.error(f"Unknown provider: {name}. Use 'auto' or one of: "
                       f"{', '.join(provider_names())}")
            return
        self.provider = name
        self.say(f"Provider set to {self.style(name, 'cyan')}")

    def cmd_model(self, arg: str) -> None:
        parts = arg.split(None, 1)
        if not parts:
            self.error("Usage: /model <provider> <model>")
            return
        name = parts[0].lower()
        if name not in provider_names():
            self.error(f"Unknown provider: {name}")
            return
        if len(parts) < 2:
            current = self.config.model_for(name)
            self.say(f"{name}: {current or '(default)'}")
            return
        self.config.set(f"providers.{name}.model", parts[1].strip())
        self.say(f"{name} model set to {self.style(parts[1].strip(), 'cyan')}")

    def cmd_clear(self) -> None:
        os.system("clear")  # noqa: S605 - fixed command, no user input

    def cmd_history(self) -> None:
        if not self.history:
            self.say(self.style("No prompts yet.", "grey"))
            return
        for index, item in enumerate(self.history, 1):
            self.say(f"  {index:>3}. {item}")

    # -- the prompt loop ---------------------------------------------------

    def prompt_text(self) -> str:
        target = "all" if self.provider == "auto" else self.provider
        return self.style(f"[{target}] › ", "magenta")

    def handle_command(self, line: str) -> bool:
        """Run a slash command. Returns False to end the session."""
        parts = line[1:].split(None, 1)
        command = parts[0].lower() if parts else ""
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command in ("quit", "exit"):
            return False
        if command == "help":
            self.cmd_help()
        elif command == "status":
            self.cmd_status()
        elif command == "providers":
            self.cmd_providers()
        elif command == "login":
            self.cmd_login(argument)
        elif command == "use":
            self.cmd_use(argument)
        elif command == "model":
            self.cmd_model(argument)
        elif command == "clear":
            self.cmd_clear()
        elif command == "history":
            self.cmd_history()
        else:
            self.error(f"Unknown command: /{command}. Try /help.")
        return True

    def ask(self, question: str) -> None:
        """Send a prompt to the selected provider(s) and print the answers."""
        self.history.append(question)

        try:
            if self.provider == "auto":
                results = self.orchestrator.auto(
                    question,
                    timeout=self.config.get("chat.timeout", 600),
                )
            else:
                model = (
                    self.config.env_override(self.provider)
                    or self.config.model_for(self.provider)
                )
                results = [
                    self.orchestrator.single_with_config(
                        self.provider, question, model=model,
                        timeout=self.config.get("chat.timeout", 600),
                    )
                ]
        except Exception as exc:  # noqa: BLE001 - never kill the REPL
            self.error(str(exc))
            return

        for result in results:
            self.header(result.provider, result.model)
            if result.ok:
                print(result.output)
            else:
                print(self.style(result.error or "unknown error", "red"))

    def run_once(self, question: str) -> None:
        """Answer a single prompt and exit. Used by the non-interactive path."""
        self.ask(question)

    def loop(self) -> None:
        """Read prompts until the user quits."""
        self._setup_readline()
        self.say(self.style(BANNER, "bold"))
        self.say()

        while self.running:
            try:
                line = input(self.prompt_text())
            except EOFError:
                self.say()
                break
            except KeyboardInterrupt:
                # Ctrl-C abandons the current line, it does not exit.
                self.say()
                continue

            line = line.strip()
            if not line:
                continue

            if line.startswith("/"):
                if not self.handle_command(line):
                    break
                continue

            self.ask(line)

        self.say(self.style("Bye.", "grey"))

    @staticmethod
    def _setup_readline() -> None:
        """Enable line editing and history when readline is available."""
        try:
            import readline
        except ImportError:
            return

        readline.set_completer(
            lambda text, state: [
                cmd for cmd in sorted(COMMANDS)
                if cmd.startswith(text)
            ][state] if any(cmd.startswith(text) for cmd in COMMANDS) else None
        )
        readline.set_completer_delims(" ")
        readline.parse_and_bind("tab: complete")
        readline.set_history_length(1000)


def run_terminal(cwd: str | None = None, provider: str | None = None,
                 question: str | None = None) -> int:
    """Entry point for the terminal interface."""
    chat = TerminalChat(cwd=cwd, default_provider=provider)

    if question:
        chat.run_once(question)
        return 0

    try:
        chat.loop()
    except KeyboardInterrupt:
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command line entry point: python -m pdfscrape.terminal"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="pdfscrape.terminal",
        description="Interactive chat with the AI providers you are signed in to.",
    )
    parser.add_argument("--provider", "-p", default=None,
                        help="Start on one provider (default: every signed-in one).")
    parser.add_argument("--question", "-q", default=None,
                        help="Ask one question and exit.")

    args = parser.parse_args(argv)
    return run_terminal(provider=args.provider, question=args.question)


if __name__ == "__main__":
    sys.exit(main())
