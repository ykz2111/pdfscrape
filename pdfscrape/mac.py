"""One-command entry point: build, run, auth, and chat.

    python -m pdfscrape.mac one            # build + auth + chat
    python -m pdfscrape.mac one --no-build  # skip the build step
    python -m pdfscrape.mac one --status    # build + auth report, no chat

This is the command a person runs on a Mac Terminal to get going. It makes
sure the package is installed, reports who is signed in, and then starts the
interactive chat.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pdfscrape.macos import build_app, open_app
from pdfscrape.providers import all_providers
from pdfscrape.terminal import TerminalChat


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ensure_installed(root: Path, quiet: bool = True) -> bool:
    """Make sure the package is importable from the repo venv.

    Returns True when the environment is ready. The venv is created and the
    package installed in editable mode if either is missing.
    """
    venv = root / ".venv"
    python = venv / "bin" / "python"

    if not python.exists():
        if not quiet:
            print(f"Creating virtual environment in {venv} ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run([str(venv / "bin" / "pip"), "install", "--upgrade", "pip"],
                       check=False)

    check = subprocess.run(
        [str(python), "-c", "import pdfscrape"],
        capture_output=True,
        cwd=str(root),
    )
    if check.returncode != 0:
        if not quiet:
            print("Installing pdfscrape ...")
        subprocess.run(
            [str(venv / "bin" / "pip"), "install", "-e", str(root)],
            check=True,
            cwd=str(root),
        )

    return True


def report_auth(chat: TerminalChat) -> None:
    """Print who is signed in, and the command for anyone who is not."""
    chat.say(chat.style("Sign-in status", "bold"))
    for provider in all_providers(cwd=chat.cwd):
        try:
            status = provider.auth()
        except Exception as exc:  # noqa: BLE001
            chat.say(f"  {provider.name:<12} {chat.style('error', 'red')}  {exc}")
            continue

        if status.logged_in:
            mark = chat.style("ok", "green")
        else:
            mark = chat.style("not signed in", "yellow")
        chat.say(f"  {provider.name:<12} {mark:<14} {chat.style(status.detail, 'grey')}")

        if not status.logged_in and status.login_hint:
            chat.say(f"  {'':<12} {chat.style('-> ' + status.login_hint, 'yellow')}")

    chat.say()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdfscrape.mac",
        description="Build, authenticate, and chat with every signed-in provider.",
    )
    parser.add_argument("--no-build", action="store_true",
                        help="Skip the venv and package setup step.")
    parser.add_argument("--status", action="store_true",
                        help="Report sign-in status and exit without chatting.")
    parser.add_argument("--app", action="store_true",
                        help="Build the double-clickable macOS .app bundle.")
    parser.add_argument("--open", dest="open_app", action="store_true",
                        help="Build and launch the macOS .app bundle.")
    parser.add_argument("--provider", "-p", default=None,
                        help="Start on one provider (default: every signed-in one).")
    parser.add_argument("--question", "-q", default=None,
                        help="Ask one question and exit.")

    args = parser.parse_args(argv)
    root = repo_root()

    if args.app:
        print(f"Built {build_app()}")
        return 0

    if args.open_app:
        print(f"Launched {open_app()}")
        return 0

    if not args.no_build:
        ensure_installed(root, quiet=False)

    chat = TerminalChat(cwd=str(root), default_provider=args.provider)

    report_auth(chat)

    if args.status:
        return 0

    if args.question:
        chat.run_once(args.question)
        return 0

    chat.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
