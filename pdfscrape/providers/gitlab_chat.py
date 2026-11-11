"""GitLab Chat provider integration."""

from pdfscrape.providers import AIProvider


class GitLabChatProvider(AIProvider):
    """GitLab Chat integration."""

    def __init__(self, gitlab_url: str = None, token: str = None):
        self.gitlab_url = gitlab_url
        self.token = token

    async def chat(self, message: str) -> str:
        """Send message via GitLab Chat."""
        # TODO: Implement GitLab Chat API
        return f"GitLab Chat: {message}"

    def configure(self, gitlab_url: str = None, token: str = None) -> None:
        """Configure GitLab Chat credentials."""
        self.gitlab_url = gitlab_url
        self.token = token
