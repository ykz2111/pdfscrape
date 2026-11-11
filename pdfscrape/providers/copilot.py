"""GitHub Copilot provider integration."""

from pdfscrape.providers import AIProvider


class CopilotProvider(AIProvider):
    """GitHub Copilot provider."""

    async def chat(self, message: str) -> str:
        """Send message to Copilot."""
        # TODO: Implement Copilot API integration
        return f"Copilot: {message}"

    def configure(self, **kwargs) -> None:
        """Configure Copilot."""
        # TODO: Setup Copilot credentials
        pass
