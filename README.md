# pdfscrape

A unified CLI that orchestrates multiple AI models and chat platforms:
- **GitHub Copilot** (code completion)
- **Claude** (reasoning, code generation)
- **Gemini** (multimodal)
- **Antigravity** (second opinions)
- **GitLab Chat** (team integration)
- **Ollama** (local models)

Claude Code / Hermes-inspired architecture for seamless multi-AI workflows.

## Quick Start

```bash
pip install -e .
pdfscrape init
pdfscrape chat "What's in this codebase?"
```

## Architecture

- `pdfscrape/cli/` - CLI commands and entrypoints
- `pdfscrape/providers/` - AI provider integrations
- `pdfscrape/chat/` - Chat and conversation management
- `pdfscrape/config/` - Configuration loading
- `tests/` - Unit and integration tests

## License

MIT
