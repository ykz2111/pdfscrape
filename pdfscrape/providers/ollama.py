"""Ollama local models provider integration."""

from pdfscrape.providers import AIProvider


class OllamaProvider(AIProvider):
    """Ollama local models provider."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def chat(self, message: str) -> str:
        """Send message to Ollama."""
        # TODO: Implement Ollama API integration
        return f"Ollama: {message}"

    def configure(self, base_url: str = None) -> None:
        """Configure Ollama."""
        if base_url:
            self.base_url = base_url
