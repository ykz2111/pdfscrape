"""Provider protocol and shared types.

Every provider in pdfscrape delegates to an already-authenticated CLI on the
machine. No provider holds or sends an API key.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Protocol


class ProviderError(RuntimeError):
    """Raised when a provider cannot complete a request."""


@dataclass
class Result:
    """Outcome of a single provider call."""

    provider: str
    ok: bool
    output: str = ""
    error: str = ""
    model: str = ""
    raw: str = ""
    exit_code: int = 0

    def __str__(self) -> str:
        return self.output if self.ok else self.error


@dataclass
class AuthStatus:
    """Login state for a provider."""

    provider: str
    logged_in: bool
    method: str = ""
    detail: str = ""
    login_hint: str = ""


@dataclass
class Provider(Protocol):
    """A provider backed by a locally authenticated CLI."""

    name: str
    binary: str

    def auth(self) -> AuthStatus:
        """Report whether the CLI is logged in."""
        ...

    def run(self, prompt: str, **kwargs: str) -> Result:
        """Send a prompt and return the result."""
        ...


@dataclass
class CommandSpec:
    """How to invoke a CLI in headless mode."""

    binary: str
    args: list[str] = field(default_factory=list)
    prompt_via: str = "arg"  # "arg" | "stdin" | "flag"
    prompt_flag: str = ""  # used when prompt_via == "flag"
    timeout: int = 600
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None


def parse_json(text: str) -> dict | None:
    """Pull a JSON document out of CLI output.

    Payloads may be pretty-printed across many lines, so the whole buffer is
    tried first and a line scan is the fallback.
    """
    text = text.strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                continue

    return None


def which(binary: str) -> str | None:
    """Resolve a binary, also checking well-known local install dirs."""
    found = shutil.which(binary)
    if found:
        return found

    extra_paths = [
        os.path.expanduser("~/.gemini/bin"),
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    for directory in extra_paths:
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return None


def run_command(
    spec: CommandSpec,
    prompt: str | None = None,
    input_text: str | None = None,
) -> tuple[str, str, int]:
    """Run a command, returning (stdout, stderr, exit_code).

    stdin is always closed so CLIs that probe for piped input do not hang.
    """
    env = os.environ.copy()
    env.update(spec.env)

    stdin_data = input_text
    if spec.prompt_via == "arg" and prompt is not None:
        args = [spec.binary, *spec.args, prompt]
    elif spec.prompt_via == "flag" and prompt is not None:
        # Some CLIs (agy) require the prompt attached to the flag itself.
        args = [spec.binary, *spec.args, f"{spec.prompt_flag}={prompt}"]
    elif prompt is not None:
        args = [spec.binary, *spec.args]
        stdin_data = prompt if input_text is None else input_text
    else:
        args = [spec.binary, *spec.args]

    try:
        proc = subprocess.run(
            args,
            input=stdin_data if stdin_data is not None else "",
            capture_output=True,
            text=True,
            timeout=spec.timeout,
            env=env,
            cwd=spec.cwd,
        )
    except FileNotFoundError as exc:
        raise ProviderError(f"{spec.binary} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderError(
            f"{spec.binary} timed out after {spec.timeout}s"
        ) from exc

    return proc.stdout, proc.stderr, proc.returncode
