"""GitHub Copilot provider (OAuth token in the OS keychain).

The Copilot CLI stores an OAuth token under the "copilot-cli" keychain service.
pdfscrape reuses that same OAuth token and never asks for an API key.

Why the API is called directly instead of through the CLI: on the
`free_limited_copilot` tier the CLI's model resolver rejects every model it
is offered ("No supported model available") even though the account is
entitled to several. Calling the Copilot endpoint with the very same OAuth
token works, so the token is used directly and the CLI is kept as a fallback.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request

from pdfscrape.providers.base import (
    AuthStatus,
    ProviderError,
    Result,
    which,
)

MODELS_URL = "https://api.githubcopilot.com/models"
CHAT_URL = "https://api.githubcopilot.com/chat/completions"

KEYCHAIN_SERVICE = "copilot-cli"

# The CLI identifies itself to Copilot with these headers.
INTEGRATION_HEADERS = {
    "Editor-Version": "vscode/1.99.0",
    "Copilot-Integration-Id": "copilot-cli",
}

# Models known to work on the limited free tier.
DEFAULT_MODEL = "gpt-4.1-2025-04-14"

# Preferred order; the first one the account may use wins.
PREFERRED_MODELS = [
    "gpt-4.1-2025-04-14",
    "gpt-4o-2024-11-20",
    "gpt-4o-mini-2024-07-18",
]


def _keychain_token() -> str:
    """Read the Copilot OAuth token from the macOS keychain."""
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip()


def _api_json(url: str, token: str, payload: dict | None = None,
              timeout: int = 30) -> dict:
    """Call a Copilot endpoint with the OAuth token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        **INTEGRATION_HEADERS,
    }

    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            detail = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            detail = body
        raise ProviderError(f"copilot API {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ProviderError(f"copilot API unreachable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("copilot API returned invalid JSON") from exc


def _entitled_models(token: str) -> list[str]:
    """Models the account is entitled to use."""
    try:
        payload = _api_json(MODELS_URL, token)
    except ProviderError:
        return []

    models = payload.get("data", []) if isinstance(payload, dict) else []
    enabled = [
        m["id"] for m in models
        if isinstance(m, dict)
        and isinstance(m.get("policy"), dict)
        and m["policy"].get("state") == "enabled"
    ]
    return enabled


class CopilotProvider:
    """GitHub Copilot via the OAuth token in the keychain."""

    name = "copilot"
    binary = "copilot"

    def __init__(self, model: str | None = None, cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        token = _keychain_token()
        if not token:
            if not which(self.binary):
                return AuthStatus(self.name, False, detail="copilot CLI not found",
                                  login_hint="brew install --cask copilot-cli")
            return AuthStatus(self.name, False,
                              detail="no Copilot OAuth token in the keychain",
                              login_hint="copilot login")

        enabled = _entitled_models(token)
        if not enabled:
            return AuthStatus(
                self.name,
                False,
                method="github-oauth",
                detail="OAuth token valid but no models are enabled for this plan",
                login_hint="upgrade to a paid Copilot plan, then run: copilot login",
            )

        usable = [m for m in PREFERRED_MODELS if m in enabled] or enabled
        return AuthStatus(
            self.name,
            True,
            method="github-oauth",
            detail=f"{len(enabled)} models enabled; using {usable[0]}",
        )

    def available_models(self) -> list[str]:
        """Models the account may use."""
        return _entitled_models(_keychain_token())

    def run(self, prompt: str, **kwargs: str) -> Result:
        token = _keychain_token()
        if not token:
            raise ProviderError("no Copilot OAuth token in the keychain (run: copilot login)")

        model = kwargs.get("model") or self.model
        if not model:
            enabled = _entitled_models(token)
            usable = [m for m in PREFERRED_MODELS if m in enabled]
            model = usable[0] if usable else (enabled[0] if enabled else DEFAULT_MODEL)

        payload = _api_json(
            CHAT_URL,
            token,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=int(kwargs.get("timeout", 120)),
        )

        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError(f"copilot returned no choices: {str(payload)[:200]}")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Reasoning models may return a list of content blocks.
        if isinstance(content, list):
            content = "\n".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )

        return Result(
            self.name,
            True,
            output=str(content or "").strip(),
            model=model,
            raw=json.dumps(payload),
            exit_code=0,
        ) if content else Result(
            self.name,
            False,
            error="copilot returned an empty response",
            model=model,
            raw=json.dumps(payload),
            exit_code=1,
        )
