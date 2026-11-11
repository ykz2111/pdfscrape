"""Gemini AI provider integration."""

from pdfscrape.providers import AIProvider


class GeminiProvider(AIProvider):
    """Google Gemini provider."""

    async def chat(self, message: str) -> str:
        """Send message to Gemini."""
        # TODO: Implement Gemini API integration
        return f"Gemini: {message}"

    def configure(self, **kwargs) -> None:
        """Configure Gemini."""
        # TODO: Setup Gemini credentials
        pass
