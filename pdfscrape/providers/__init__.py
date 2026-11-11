"""Provider registry.

All providers authenticate through a locally signed-in CLI (OAuth or a local
model). pdfscrape never handles an API key.
"""

from __future__ import annotations

from pdfscrape.providers.antigravity import AntigravityProvider, GeminiProvider
from pdfscrape.providers.base import (
    AuthStatus,
    Provider,
    ProviderError,
    Result,
)
from pdfscrape.providers.claude import ClaudeProvider
from pdfscrape.providers.codex import CodexProvider
from pdfscrape.providers.copilot import CopilotProvider
from pdfscrape.providers.gitlab_chat import GitLabChatProvider
from pdfscrape.providers.ollama import OllamaProvider

__all__ = [
    "AntigravityProvider",
    "AuthStatus",
    "ClaudeProvider",
    "CodexProvider",
    "CopilotProvider",
    "GeminiProvider",
    "GitLabChatProvider",
    "OllamaProvider",
    "Provider",
    "ProviderError",
    "Result",
    "build_provider",
    "provider_names",
    "all_providers",
]

_FACTORIES = {
    "antigravity": AntigravityProvider,
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "copilot": CopilotProvider,
    "gemini": GeminiProvider,
    "gitlab": GitLabChatProvider,
    "gitlab-chat": GitLabChatProvider,
    "ollama": OllamaProvider,
}


def provider_names() -> list[str]:
    """Canonical provider names, in display order."""
    return ["codex", "claude", "antigravity", "copilot", "gitlab", "ollama"]


def build_provider(name: str, model: str | None = None,
                   cwd: str | None = None) -> Provider:
    """Instantiate a provider by name."""
    key = (name or "").strip().lower()
    if key not in _FACTORIES:
        raise ProviderError(
            f"unknown provider '{name}'. Available: {', '.join(provider_names())}"
        )

    factory = _FACTORIES[key]
    # Only pass a model when one was requested, so each provider keeps its
    # own default instead of receiving None.
    if model:
        return factory(model=model, cwd=cwd)
    return factory(cwd=cwd)


def all_providers(cwd: str | None = None) -> list[Provider]:
    """Instantiate every provider for status reporting."""
    providers = []
    for name in provider_names():
        factory = _FACTORIES[name]
        providers.append(factory(cwd=cwd))
    return providers
