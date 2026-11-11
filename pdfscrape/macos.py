"""Build a double-clickable macOS app that opens pdfscrape in Terminal.

The app bundle is the macOS equivalent of the OpenCode plugin: one artifact
that starts the terminal chat with every provider already signed in.

    python -m pdfscrape.macos build     # create dist/pdfscrape.app
    python -m pdfscrape.macos install   # copy it to /Applications
    python -m pdfscrape.macos open      # build if needed, then launch
"""

from __future__ import annotations

import argparse
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path

APP_NAME = "pdfscrape"
BUNDLE_ID = "com.pdfscrape.terminal"

INFO_PLIST = {
    "CFBundleName": "pdfscrape",
    "CFBundleDisplayName": "pdfscrape",
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleVersion": "0.1.0",
    "CFBundleShortVersionString": "0.1.0",
    "CFBundlePackageType": "APPL",
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleExecutable": "pdfscrape",
    "CFBundleIconFile": "AppIcon",
    "LSMinimumSystemVersion": "11.0",
    # A terminal tool, so do not steal focus with a Dock icon.
    "LSUIElement": True,
    "NSHighResolutionCapable": True,
}

# The launcher runs inside the app bundle. It finds the repo, makes sure the
# venv exists, then hands over to the Python CLI in terminal mode.
LAUNCHER = """#!/bin/bash
# pdfscrape launcher — opens the terminal chat.
set -uo pipefail

REPO="__REPO__"

if [ ! -d "$REPO" ]; then
  osascript -e "display alert \\"pdfscrape\\" message \\"Repo not found at $REPO.\\" as critical"
  exit 1
fi

VENV="$REPO/.venv"
PY="$VENV/bin/python"

# Create the venv on first run. This needs the network for pip, so it is only
# done when the venv is missing.
if [ ! -x "$PY" ]; then
  osascript -e 'display notification "Building pdfscrape..." with title "pdfscrape"'
  python3 -m venv "$VENV" 2>/dev/null || {
    osascript -e 'display alert "pdfscrape" message "Could not create a venv." as critical'
    exit 1
  }
  "$VENV/bin/pip" install --upgrade pip >/dev/null 2>&1
fi

# Make sure the package itself is importable from the venv.
if ! "$PY" -c "import pdfscrape" >/dev/null 2>&1; then
  "$VENV/bin/pip" install -e "$REPO" >/dev/null 2>&1
fi

# Open a Terminal window running the chat.
PROMPT="$REPO/.venv/bin/pdfscrape-terminal"
if [ ! -x "$PROMPT" ]; then
  PROMPT="exec $PY -m pdfscrape.terminal"
fi

# The command is handed to osascript as an argv element rather than pasted
# into AppleScript source, so no quoting or escaping is needed for it.
osascript -e 'on run argv' \\
          -e 'tell application "Terminal"' \\
          -e 'activate' \\
          -e 'do script (item 1 of argv)' \\
          -e 'end tell' \\
          -e 'end run' "$PROMPT" >/dev/null
"""


def repo_root() -> Path:
    """The directory holding the pdfscrape package."""
    return Path(__file__).resolve().parent.parent


def build_app(output: Path | None = None) -> Path:
    """Create the .app bundle and return its path."""
    root = repo_root()
    output = output or (root / "dist" / f"{APP_NAME}.app")

    if output.exists():
        shutil.rmtree(output)

    contents = output / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    launcher = macos / APP_NAME
    # A plain replace, not str.format: the launcher is full of shell braces.
    launcher.write_text(LAUNCHER.replace("__REPO__", str(root)))
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    with open(contents / "Info.plist", "wb") as fh:
        plistlib.dump(INFO_PLIST, fh)

    _write_icon(resources / "AppIcon.icns")

    return output


def _write_icon(target: Path) -> None:
    """Give the app an icon, falling back to the system one."""
    system_icon = Path(
        "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/"
        "GenericApplicationIcon.icns"
    )
    if system_icon.exists():
        shutil.copyfile(system_icon, target)


def install_app(app: Path | None = None) -> Path:
    """Copy the app into /Applications."""
    app = app or build_app()
    target = Path("/Applications") / app.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(app, target)
    return target


def open_app(app: Path | None = None) -> Path:
    """Build if needed, then launch the app."""
    app = app or build_app()
    subprocess.run(["open", str(app)], check=False)
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pdfscrape.macos",
        description="Build and launch the pdfscrape macOS terminal app.",
    )
    sub = parser.add_subparsers(dest="command")

    build_cmd = sub.add_parser("build", help="Create the .app bundle in dist/.")
    build_cmd.add_argument("--output", type=Path, default=None)

    install_cmd = sub.add_parser("install", help="Copy the app to /Applications.")
    install_cmd.add_argument("--output", type=Path, default=None)

    open_cmd = sub.add_parser("open", help="Build if needed and launch the app.")
    open_cmd.add_argument("--output", type=Path, default=None)

    args = parser.parse_args(argv)
    command = args.command or "build"

    if command == "build":
        path = build_app(getattr(args, "output", None))
        print(f"Built {path}")
    elif command == "install":
        path = install_app(getattr(args, "output", None))
        print(f"Installed {path}")
    else:
        path = open_app(getattr(args, "output", None))
        print(f"Launched {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
