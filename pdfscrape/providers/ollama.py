"""Ollama provider (local models, no auth).

Uses the ollama CLI so the request stays on the machine and needs no key.
"""

from __future__ import annotations

import re

from pdfscrape.providers.base import (
    AuthStatus,
    CommandSpec,
    ProviderError,
    Result,
    run_command,
    which,
)

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


class OllamaProvider:
    """Local models through the Ollama CLI."""

    name = "ollama"
    binary = "ollama"

    def __init__(self, model: str = "smollm2:latest", cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        if not which(self.binary):
            return AuthStatus(self.name, False, detail="ollama not found",
                              login_hint="brew install ollama")

        spec = CommandSpec(binary=which(self.binary) or self.binary,
                           args=["list"], timeout=30)
        stdout, stderr, code = run_command(spec)

        if code != 0:
            return AuthStatus(self.name, False,
                              detail="ollama daemon not reachable (is it running?)",
                              login_hint="ollama serve")

        models = [
            ln.split()[0]
            for ln in stdout.splitlines()[1:]
            if ln.strip()
        ]
        if not models:
            return AuthStatus(self.name, False, detail="no models pulled",
                              login_hint="ollama pull smollm2")

        return AuthStatus(self.name, True, method="local",
                          detail=f"{len(models)} local models: {', '.join(models[:5])}")

    def available_models(self) -> list[str]:
        spec = CommandSpec(binary=which(self.binary) or self.binary,
                           args=["list"], timeout=30)
        stdout, _, _ = run_command(spec)
        return [ln.split()[0] for ln in stdout.splitlines()[1:] if ln.strip()]

    def run(self, prompt: str, **kwargs: str) -> Result:
        model = kwargs.get("model") or self.model
        spec = CommandSpec(
            binary=which(self.binary) or self.binary,
            args=["run", model],
            timeout=int(kwargs.get("timeout", 600)),
            cwd=kwargs.get("cwd") or self.cwd,
        )

        stdout, stderr, code = run_command(spec, prompt=prompt)

        text = ANSI.sub("", stdout).strip()
        if code != 0 and not text:
            detail = (stderr or stdout).strip()[-500:]
            raise ProviderError(f"ollama failed: {detail}")

        return Result(self.name, True, output=text, model=model,
                      raw=stdout, exit_code=code)
