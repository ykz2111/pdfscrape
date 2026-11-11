"""Antigravity (Google Gemini) second opinion provider."""

from pdfscrape.providers import AIProvider


class AntigravityProvider(AIProvider):
    """Antigravity second opinion provider."""

    async def chat(self, message: str) -> str:
        """Get second opinion from Antigravity."""
        # TODO: Implement Antigravity integration
        return f"Antigravity: {message}"

    def configure(self, **kwargs) -> None:
        """Configure Antigravity."""
        # TODO: Setup Antigravity credentials
        pass
