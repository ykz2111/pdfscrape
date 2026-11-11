"""Claude AI provider integration."""

from pdfscrape.providers import AIProvider


class ClaudeProvider(AIProvider):
    """Claude AI provider."""

    async def chat(self, message: str) -> str:
        """Send message to Claude."""
        # TODO: Implement Claude API integration
        return f"Claude: {message}"

    def configure(self, **kwargs) -> None:
        """Configure Claude."""
        # TODO: Setup Claude credentials
        pass
