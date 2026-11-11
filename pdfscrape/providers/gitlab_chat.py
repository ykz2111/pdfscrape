"""GitLab Chat provider (OAuth via glab).

GitLab's own /api/v4/chat/completions endpoint is internal-use-only on
GitLab.com and requires team membership. The supported path for a user is the
GitLab Duo CLI reached through `glab duo cli run`, which reuses the glab OAuth
token stored in the OS keyring.

Output: {"status":"success","response":"...","sessionId":"..."}
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


def _parse_json(text: str) -> dict | None:
    """Pull a JSON document out of CLI output."""
    return parse_json(text)


class GitLabChatProvider:
    """GitLab Chat through `glab duo cli run`."""

    name = "gitlab"
    binary = "glab"

    def __init__(self, model: str | None = None, cwd: str | None = None):
        self.model = model
        self.cwd = cwd

    def auth(self) -> AuthStatus:
        path = which(self.binary)
        if not path:
            return AuthStatus(self.name, False, detail="glab not found",
                              login_hint="brew install glab")

        spec = CommandSpec(binary=path, args=["auth", "status"], timeout=60)
        stdout, stderr, code = run_command(spec)

        # glab writes its auth report to stderr, not stdout.
        report = f"{stdout}\n{stderr}"

        if code != 0 or "Logged in" not in report:
            return AuthStatus(self.name, False,
                              detail="glab is not authenticated",
                              login_hint="glab auth login")

        host = ""
        for line in report.splitlines():
            if "Logged in" in line:
                # "  ✓ Logged in to gitlab.com as ykz21 (keyring)"
                cleaned = line.replace("✓", "").strip()
                if " to " in cleaned:
                    cleaned = cleaned.split(" to ", 1)[1]
                host = cleaned.split(" as ")[0].strip()
                break

        return AuthStatus(
            self.name,
            True,
            method="gitlab-oauth",
            detail=f"glab authenticated{(' to ' + host) if host else ''}",
        )

    def run(self, prompt: str, **kwargs: str) -> Result:
        args = ["duo", "cli", "run", "--output-format", "json"]
        model = kwargs.get("model") or self.model
        if model:
            args += ["--model", model]
        # --goal must come last so the prompt positional lands right after it.
        args += ["--goal"]

        spec = CommandSpec(
            binary=which(self.binary) or self.binary,
            args=args,
            timeout=int(kwargs.get("timeout", 900)),
            cwd=kwargs.get("cwd") or self.cwd,
        )

        stdout, stderr, code = run_command(spec, prompt=prompt)

        payload = _parse_json(stdout)

        if payload is None:
            # The Duo CLI logs to stderr; keep only the tail for the message.
            detail = stderr.strip()[-500:] if stderr else stdout.strip()[-500:]
            raise ProviderError(f"glab duo returned no JSON output: {detail}")

        if payload.get("status") != "success":
            return Result(self.name, False,
                          error=str(payload.get("response") or "duo run failed"),
                          model=model or "", raw=stdout, exit_code=code or 1)

        return Result(self.name, True, output=str(payload.get("response", "")).strip(),
                      model=model or "", raw=stdout, exit_code=code)
