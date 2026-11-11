"""AI provider integrations."""

from typing import Protocol


class AIProvider(Protocol):
    """Base interface for AI providers."""

    async def chat(self, message: str) -> str:
        """Send message and get response."""
        ...

    def configure(self, **kwargs) -> None:
        """Configure provider with credentials."""
        ...
