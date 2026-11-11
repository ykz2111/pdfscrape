"""Orchestration: run a prompt across one or many providers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from pdfscrape.providers import (
    ProviderError,
    Result,
    build_provider,
    provider_names,
)


class Orchestrator:
    """Routes a prompt to providers and collects their answers."""

    def __init__(self, cwd: str | None = None):
        self.cwd = cwd

    def single(self, name: str, prompt: str, model: str | None = None,
               timeout: int | None = None) -> Result:
        """Send the prompt to one provider."""
        provider = build_provider(name, model=model, cwd=self.cwd)
        kwargs = {"cwd": self.cwd}
        if timeout:
            kwargs["timeout"] = timeout
        return provider.run(prompt, **kwargs)

    def single_with_config(self, name: str, prompt: str, model: str | None = None,
                           timeout: int | None = None) -> Result:
        """Send the prompt to one provider, resolving its model from config."""
        from pdfscrape.config import Config

        config = Config()
        resolved = (
            model
            or config.env_override(name)
            or config.model_for(name)
        )
        return self.single(name, prompt, model=resolved, timeout=timeout)

    def many(self, names: list[str], prompt: str, model: str | None = None,
             timeout: int | None = None) -> list[Result]:
        """Send the prompt to several providers concurrently.

        A provider that fails does not abort the others; its error is reported
        in the returned list.
        """
        if not names:
            raise ProviderError("no providers requested")

        def work(name: str) -> Result:
            try:
                return self.single(name, prompt, model=model, timeout=timeout)
            except ProviderError as exc:
                return Result(name, False, error=str(exc))
            except Exception as exc:  # noqa: BLE001 - report, never abort
                return Result(name, False, error=f"{type(exc).__name__}: {exc}")

        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            return list(pool.map(work, names))

    def auto(self, prompt: str, model: str | None = None,
             timeout: int | None = None) -> list[Result]:
        """Ask every provider that is currently logged in."""
        from pdfscrape.providers import all_providers

        ready = []
        for provider in all_providers(cwd=self.cwd):
            try:
                status = provider.auth()
            except Exception:  # noqa: BLE001
                continue
            if status.logged_in:
                ready.append(provider.name)

        if not ready:
            raise ProviderError(
                "no providers are signed in. Run 'pdfscrape login --all' first."
            )

        return self.many(ready, prompt, model=model, timeout=timeout)


def resolve_providers(spec: str | None) -> list[str]:
    """Turn a --provider string into a list of provider names.

    Accepts "auto", a comma separated list, or "all".
    """
    if not spec or spec.strip().lower() == "auto":
        return ["auto"]

    names = []
    for part in spec.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part == "all":
            names.extend(provider_names())
        else:
            names.append(part)
    return names or ["auto"]
