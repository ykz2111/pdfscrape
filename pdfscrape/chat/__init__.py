"""Chat and conversation orchestration."""


class Orchestrator:
    """Orchestrates multiple AI providers."""

    def __init__(self):
        self.providers = {}

    def register(self, name: str, provider):
        """Register an AI provider."""
        self.providers[name] = provider

    async def chat(self, message: str, provider: str = "auto"):
        """Send message to specified or best provider."""
        if provider == "auto":
            # TODO: Implement intelligent provider selection
            provider = "claude"

        if provider not in self.providers:
            raise ValueError(f"Unknown provider: {provider}")

        return await self.providers[provider].chat(message)
