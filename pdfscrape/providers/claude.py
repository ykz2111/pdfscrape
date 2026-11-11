"""Claude Code provider (Anthropic OAuth).

Requires `claude login`. Without it the CLI prints
"Not logged in - Please run /login" and exits non-zero.
"""

from __future__ import annotations

import json

from pdfscrape.providers.base import (
    AuthStatus,
    CommandSpec,
    ProviderError,
    Result,
    parse_json,
    run_command,
    which,
)


class ClaudeProvider:
    """Claude Code via the local CLI's Anthropic OAuth session."""

    name = "claude"
    binary = "claude"

    def __init__(self, model: str | None = None, cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        path = which(self.binary)
        if not path:
            return AuthStatus(self.name, False, detail="claude CLI not found",
                              login_hint="npm i -g @anthropic-ai/claude-code")

        spec = CommandSpec(binary=path, args=["auth", "status"], timeout=60)
        stdout, stderr, code = run_command(spec)

        payload = None
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        if payload and payload.get("loggedIn"):
            return AuthStatus(
                self.name,
                True,
                method=str(payload.get("authMethod") or "oauth"),
                detail="Anthropic OAuth session active",
            )

        detail = "not logged in"
        if payload and payload.get("authMethod"):
            detail = f"not logged in (authMethod={payload['authMethod']})"

        return AuthStatus(self.name, False, method="none", detail=detail,
                          login_hint="claude login")

    def run(self, prompt: str, **kwargs: str) -> Result:
        args = ["-p", "--output-format", "json"]
        model = kwargs.get("model") or self.model
        if model:
            args += ["--model", model]

        spec = CommandSpec(
            binary=which(self.binary) or self.binary,
            args=args,
            timeout=int(kwargs.get("timeout", 600)),
            cwd=kwargs.get("cwd") or self.cwd,
        )

        stdout, stderr, code = run_command(spec, prompt=prompt)

        payload = parse_json(stdout)

        if payload is None:
            if "Not logged in" in stdout or "Not logged in" in stderr:
                return Result(self.name, False, error="Not logged in. Run: claude login",
                              exit_code=code or 1)
            detail = (stderr or stdout).strip()[-500:]
            raise ProviderError(f"claude returned no JSON output: {detail}")

        if payload.get("is_error"):
            return Result(self.name, False,
                          error=str(payload.get("result") or "claude error"),
                          model=model, raw=stdout, exit_code=code or 1)

        output = payload.get("result")
        if isinstance(output, list):
            output = "\n".join(
                block.get("text", "") for block in output if isinstance(block, dict)
            )

        return Result(self.name, True, output=str(output or "").strip(),
                      model=model or str(payload.get("model", "")),
                      raw=stdout, exit_code=code)
