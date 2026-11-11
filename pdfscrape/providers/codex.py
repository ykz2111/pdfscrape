"""Codex CLI provider (ChatGPT OAuth).

Codex is authenticated with a ChatGPT account (~/.codex/auth.json, auth_mode
"chatgpt"). The installed config.toml may redirect openai_base_url to a local
Ollama proxy, so the real backend URL is forced to the ChatGPT Codex endpoint.

Models available to a ChatGPT account are gpt-6.x / gpt-5.6 variants; the
codex-* aliases are rejected by the server for ChatGPT plans.
"""

from __future__ import annotations

import json
import os

from pdfscrape.providers.base import (
    AuthStatus,
    CommandSpec,
    ProviderError,
    Result,
    run_command,
    which,
)

CHATGPT_CODEX_URL = "https://chatgpt.com/backend-api/codex"

# Models the ChatGPT-backed Codex endpoint accepts (verified against the
# account's model catalog).
CHATGPT_MODELS = [
    "gpt-6.1-sol",
    "gpt-6-astra",
    "gpt-6-terra",
    "gpt-6-sol",
    "gpt-6-luna",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
]


def _config_override(key: str, value: str) -> str:
    return f"-c{key}={value}"


class CodexProvider:
    """Codex via the local CLI's ChatGPT OAuth session."""

    name = "codex"
    binary = "codex"

    def __init__(self, model: str = "gpt-6.1-sol", cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        path = which(self.binary)
        if not path:
            return AuthStatus(self.name, False, detail="codex CLI not found",
                              login_hint="npm i -g @openai/codex")

        auth_file = os.path.expanduser("~/.codex/auth.json")
        try:
            with open(auth_file) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return AuthStatus(self.name, False, detail="no auth.json",
                              login_hint="codex login")

        mode = data.get("auth_mode", "")
        if mode != "chatgpt":
            return AuthStatus(
                self.name,
                False,
                method=f"api-key({mode})" if mode else "",
                detail="Codex is not signed in with a ChatGPT account",
                login_hint="codex login",
            )

        return AuthStatus(
            self.name,
            True,
            method="chatgpt-oauth",
            detail=f"ChatGPT account OAuth token present (auth_mode={mode})",
        )

    def run(self, prompt: str, **kwargs: str) -> Result:
        model = kwargs.get("model") or self.model
        args = [
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-C",
            kwargs.get("cwd") or self.cwd or os.getcwd(),
            _config_override("openai_base_url", json.dumps(CHATGPT_CODEX_URL)),
            "-m",
            model,
        ]

        spec = CommandSpec(
            binary=which(self.binary) or self.binary,
            args=args,
            timeout=int(kwargs.get("timeout", 900)),
            cwd=kwargs.get("cwd") or self.cwd,
        )

        stdout, stderr, code = run_command(spec, prompt=prompt)

        messages: list[str] = []
        errors: list[str] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            kind = event.get("type")
            if kind == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message" and item.get("text"):
                    messages.append(item["text"])
            elif kind == "turn.failed":
                errors.append(event.get("error", {}).get("message", "turn failed"))
            elif kind == "error":
                errors.append(event.get("message", "error"))

        if errors:
            message = errors[-1]
            if "usage limit" in message.lower():
                message = (
                    f"{message} (the ChatGPT subscription for this Codex "
                    "account is out of quota; wait for the reset or upgrade)"
                )
            return Result(self.name, False, error=message, model=model,
                          raw=stdout, exit_code=code or 1)

        if not messages:
            detail = (stderr or stdout).strip()[-500:]
            raise ProviderError(f"codex returned no message: {detail}")

        return Result(self.name, True, output="\n".join(messages).strip(),
                      model=model, raw=stdout, exit_code=code)
