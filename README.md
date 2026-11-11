# pdfscrape

One CLI for every AI provider you are already signed in to.

pdfscrape does **not** use API keys. Every provider is reached through the
CLI that already holds your OAuth session, so there is nothing to paste into a
config file and nothing to leak.

```bash
pdfscrape init                          # who is signed in, and how
pdfscrape chat "explain this repo"      # ask every signed-in provider
pdfscrape chat "explain this repo" -p claude
pdfscrape chat "summarize this diff" -p codex,antigravity --json
```

## Providers

| Provider | How it is reached | Sign in with |
|---|---|---|
| `codex` | `codex exec --json` | `codex login` (ChatGPT account) |
| `claude` | `claude -p --output-format json` | `claude login` |
| `antigravity` | `agy -p=... --output-format json` | sign in to Antigravity with Google |
| `copilot` | keychain OAuth token → Copilot API | `copilot login` |
| `gitlab` | `glab duo cli run --goal` | `glab auth login` |
| `ollama` | `ollama run` | nothing, runs locally |

`pdfscrape login --all` prints the sign-in command for each provider.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pdfscrape init
```

Requires Python 3.9+ and the provider CLIs on `PATH`.

## Notes per provider

These are real constraints found while wiring each provider up, not guesses.

- **codex** — the installed `~/.codex/config.toml` may point `openai_base_url`
  at a local Ollama proxy. pdfscrape overrides it to
  `https://chatgpt.com/backend-api/codex` so the ChatGPT OAuth session is used.
  Only the `gpt-6.x` / `gpt-5.6` models work with a ChatGPT plan; the
  `codex-*` aliases are rejected by the server.
- **gemini** — Google retired "Gemini Code Assist for individuals"; the Gemini
  CLI now refuses those accounts (`UNSUPPORTED_CLIENT`). Use `antigravity`.
- **antigravity** — the `agy` binary lives in `~/.gemini/bin`, which is not
  always on `PATH`; pdfscrape looks there. The prompt must be attached to the
  flag (`-p=...`), not passed as a separate argument.
- **copilot** — on the `free_limited_copilot` tier the Copilot CLI's model
  resolver rejects every model it is offered ("No supported model available"),
  even though the account is entitled to several. pdfscrape therefore reads
  the same keychain OAuth token and calls the Copilot API directly. It is
  still the OAuth token, never an API key.
- **gitlab** — GitLab's `/api/v4/chat/completions` endpoint is internal-use-only
  on GitLab.com and requires team membership. The supported path is the Duo
  CLI via `glab duo cli run`, which reuses the glab OAuth token in the
  keyring. Note that `glab auth status` prints to **stderr**, not stdout.
- **ollama** — purely local; no auth and no network.

## Configuration

`~/.pdfscrape/config.yaml` (created on first run):

```yaml
providers:
  codex:
    model: gpt-6.1-sol
  antigravity:
    model: gemini-3.8-flash-high
  ollama:
    model: smollm2:latest
chat:
  default_provider: auto
  timeout: 600
```

Override per call with `-m/--model`, or per shell with
`PDFSCRAPE_<PROVIDER>_MODEL`.

## OpenCode plugin

`plugins/pdfscrape.js` exposes the providers as OpenCode tools, so any
OpenCode session can reach the providers you are signed in to.

```bash
cp plugins/pdfscrape.js ~/.config/opencode/plugins/pdfscrape.js
```

OpenCode reloads plugins on save; use `/reload` to force it.

| Tool | Purpose |
|---|---|
| `pdfscrape.ask(provider, prompt)` | ask one provider |
| `pdfscrape.ask_all(prompt)` | ask every signed-in provider |
| `pdfscrape.status()` | who is signed in, and how |

The plugin shells out to the `pdfscrape` CLI rather than reimplementing
provider calls, so the OAuth handling lives in one place. It finds the CLI via
`PDFSCRAPE_BIN`, then the repo venv, then `PATH`.

## Layout

```
pdfscrape/
├── cli/          command definitions (init, chat, login, providers)
├── providers/    one module per provider; all delegate to a signed-in CLI
├── chat/         orchestration: single, multi, and auto routing
├── config/       YAML config with env overrides
└── plugins/      OpenCode plugin exposing the providers as tools
```

## Development

```bash
.venv/bin/ruff check pdfscrape/ tests/
.venv/bin/python -m pytest tests/ -q
```

## License

MIT
