"""Antigravity provider (Google OAuth via the agy CLI).

The Antigravity CLI lives at ~/.gemini/bin/agy and is authenticated with the
same Google account as the Gemini CLI. It is the supported replacement for the
retired "Gemini Code Assist for individuals" tier.

Output: {"status":"SUCCESS","response":"...","usage":{...}}
"""

from __future__ import annotations

from pdfscrape.providers.base import (
    AuthStatus,
    CommandSpec,
    ProviderError,
    Result,
    parse_json,
    run_command,
    which,
)


class AntigravityProvider:
    """Antigravity via the local `agy` CLI."""

    name = "antigravity"
    binary = "agy"

    def __init__(self, model: str = "gemini-3.8-flash-high", cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        path = which(self.binary)
        if not path:
            return AuthStatus(self.name, False, detail="agy CLI not found",
                              login_hint="open the Antigravity IDE and sign in with Google")

        spec = CommandSpec(binary=path, args=["models"], timeout=60)
        stdout, stderr, code = run_command(spec)

        if code != 0 or "Fetching available models" in stdout and not stdout.strip():
            return AuthStatus(self.name, False, detail="agy models failed",
                              login_hint="sign in to Antigravity with Google")

        models = [ln.split("\t")[0].strip() for ln in stdout.splitlines()
                  if "\t" in ln]
        if not models:
            return AuthStatus(self.name, False,
                              detail="agy returned no models (not signed in?)",
                              login_hint="sign in to Antigravity with Google")

        return AuthStatus(
            self.name,
            True,
            method="google-oauth",
            detail=f"{len(models)} models available via Google OAuth",
        )

    def run(self, prompt: str, **kwargs: str) -> Result:
        model = kwargs.get("model") or self.model
        args = ["--output-format", "json"]
        if model:
            args += ["--model", model]

        spec = CommandSpec(
            binary=which(self.binary) or self.binary,
            args=args,
            prompt_via="flag",
            prompt_flag="-p",
            timeout=int(kwargs.get("timeout", 600)),
            cwd=kwargs.get("cwd") or self.cwd,
        )

        stdout, stderr, code = run_command(spec, prompt=prompt)

        payload = parse_json(stdout)

        if payload is None:
            detail = (stderr or stdout).strip()[-500:]
            raise ProviderError(f"agy returned no JSON output: {detail}")

        if payload.get("status") != "SUCCESS":
            return Result(self.name, False,
                          error=str(payload.get("response") or payload.get("status")),
                          model=model, raw=stdout, exit_code=code or 1)

        return Result(self.name, True, output=str(payload.get("response", "")).strip(),
                      model=model, raw=stdout, exit_code=code)


# The Gemini CLI is no longer offered for accounts on the retired free tier.
# Keep a provider entry so `pdfscrape providers` can explain why it is off.
class GeminiProvider:
    """Gemini CLI provider (legacy).

    Google retired "Gemini Code Assist for individuals"; the Gemini CLI now
    rejects those accounts with UNSUPPORTED_CLIENT. Antigravity replaces it.
    """

    name = "gemini"
    binary = "gemini"

    def auth(self) -> AuthStatus:
        if not which(self.binary):
            return AuthStatus(self.name, False, detail="gemini CLI not found",
                              login_hint="npm i -g @google/gemini-cli")
        return AuthStatus(
            self.name,
            False,
            method="google-oauth",
            detail=(
                "This Google account is on the retired 'Gemini Code Assist for "
                "individuals' tier; the Gemini CLI rejects it. Use the "
                "antigravity provider instead."
            ),
            login_hint="pdfscrape chat --provider antigravity",
        )

    def run(self, prompt: str, **kwargs: str) -> Result:
        raise ProviderError(
            "gemini CLI is unavailable for this account tier. "
            "Use --provider antigravity."
        )
