# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

`pdfscrape` is a CLI and multi-agent toolkit that routes prompts to locally
authenticated AI providers and bundles a curated library of **259 skills**,
**41 specialized subagents**, and **62 plugins** (OpenCode, Hermes, and Claude
marketplace plugins).

It is a thin orchestration layer: **it never holds an API key**. Each provider
shells out to a CLI that already carries the user's OAuth session.

`plugins/pdfscrape.js` exposes the same providers as OpenCode tools with
accessible Markdown output.

## Non-negotiable design rule

Do not add API-key handling, `.env` loading of provider tokens, or new
provider endpoints that require a pasted secret. If a provider needs
credentials, it must reuse an existing signed-in CLI or a token already in the
OS keychain. Never commit `.env` files, shell histories, or home-directory
secrets.

Adding a provider means adding a module under `pdfscrape/providers/` that
implements `auth()` and `run()`, then registering it in `_FACTORIES` in
`pdfscrape/providers/__init__.py`. Also add it to `provider_names()` so
`pdfscrape init` reports it, and to the `PROVIDERS` list in
`plugins/pdfscrape.js` so the OpenCode tool accepts it.

## Commands

```bash
.venv/bin/pdfscrape init                        # provider login status
.venv/bin/pdfscrape chat "prompt"               # every signed-in provider
.venv/bin/pdfscrape chat "prompt" -p claude     # one provider
.venv/bin/pdfscrape chat "prompt" --json        # machine readable
.venv/bin/ruff check pdfscrape/ tests/          # lint
.venv/bin/python -m pytest tests/ -q            # tests
```

The venv is at `.venv/`. The system `pip` is too old for PEP 660 editable
installs, so `pip install -e .` needs the venv's upgraded pip.

## Provider gotchas that will waste your time

These were each found by testing against real CLIs. They still apply.

- **Never assume a CLI's JSON output is one object per line.** `claude`,
  `agy`, and `glab duo` all emit pretty-printed multi-line JSON. Use
  `parse_json()` from `providers/base.py`, which handles both shapes. Codex is
  the exception: it really does emit one JSON object per line.
- **A CLI's flag parsing differs.** `agy` requires the prompt attached to the
  flag (`-p=...`); passing it as a separate argument silently uses the next
  argument as the prompt. `glab duo cli run` wants `--goal <value>` as two
  argv entries — the `=` form is not parsed.
- **`glab auth status` writes to stderr.** Reading only stdout makes a
  logged-in user look logged out.
- **`copilot` needs the `Editor-Version` and `Copilot-Integration-Id`
  headers** or the models endpoint 404s.
- **Do not trust `~/.codex/config.toml`.** It may redirect `openai_base_url`
  at a local Ollama proxy. Override it to the ChatGPT Codex endpoint.
- **Do not pass `model=None` into a provider constructor.** It overrides the
  provider's own default and lands in the argv as `None`. `build_provider()`
  omits the argument when no model is given.

## Adding a provider

1. Create `pdfscrape/providers/<name>.py`.
2. Implement `auth()` returning an `AuthStatus`. When not signed in, always
   fill in `login_hint` — `pdfscrape init` prints it.
3. Implement `run(prompt, **kwargs)` returning a `Result`. Return a failed
   `Result` for provider-side errors; raise `ProviderError` only for local
   problems like a missing binary.
4. Register in `_FACTORIES` and add to `provider_names()`.
5. Add the sign-in command to the `hints` dict in `cli/commands.py`.
6. Add the name to `PROVIDERS` in `plugins/pdfscrape.js`.

## The macOS terminal

`pdfscrape.mac` at the repo root is the one command a person runs on a Mac
Terminal: it creates the venv if missing, installs the package, reports the
sign-in status, and starts the interactive chat.

```
./pdfscrape.mac              build, report sign-in status, start the chat
./pdfscrape.mac status       build and report sign-in status only
./pdfscrape.mac ask "..."    ask one question and exit
./pdfscrape.mac app          build the double-clickable .app bundle
./pdfscrape.mac install      copy the .app into /Applications
```

The pieces behind it:

- `pdfscrape/terminal.py` — the REPL. Colour is decoration only; every status
  is also spelled out in words so the output survives being piped or read by
  someone who cannot see colour.
- `pdfscrape/macos.py` — builds `dist/pdfscrape.app`. The launcher is a shell
  script embedded in a Python string, so **it is not a format string**: use
  `str.replace`, never `str.format`. Shell braces break `.format`. The same
  applies to the AppleScript: pass the command as an argv element to
  `osascript` rather than pasting it into the source, so no escaping is
  needed.
- `pdfscrape/mac.py` — the Python entry point behind the shell wrapper.

Entry points are declared in `pyproject.toml`: `pdfscrape`,
`pdfscrape-terminal`, and `pdfscrape-mac`. Adding one means adding a console
script there and reinstalling with `pip install -e .`.

## The OpenCode plugin

`plugins/pdfscrape.js` is installed at
`~/.config/opencode/plugins/pdfscrape.js` and referenced in `opencode.json`. It
registers three tools:

| Tool | Purpose |
|---|---|
| `pdfscrape.ask(provider, prompt)` | ask one provider |
| `pdfscrape.ask_all(prompt)` | ask every signed-in provider |
| `pdfscrape.status()` | who is signed in, and how |

The plugin **shells out to this CLI** rather than reimplementing provider
calls. Every provider quirk listed above is handled by the Python side, so
there is one place to maintain them. Keep it that way: if you add a provider
behaviour, change `pdfscrape/providers/`, not the plugin.

Output from `formatResults()` uses accessible Markdown (`#` / `##` headings,
explicit `Status: succeeded` / `Status: failed` lines, and fenced code blocks)
so screen readers and plain-text consumers never depend on colour or emoji.

OpenCode's V2 plugin API expects the default export to be an object with `id`
and `setup`, not a bare function. To apply plugin or config edits, OpenCode
reloads automatically on save, or run `/reload`.

## Absorbed Skills, Agents, and Plugins

All skills, subagents, and plugins from local Claude and Hermes installations
are absorbed into this repository and synced to `~/.config/opencode/`:

### 1. Skills (`skills/` and `~/.config/opencode/skills/`)

259 `SKILL.md` definitions organized at root level and by domain category,
discovered automatically via `opencode.json`:

- **Core design & engineering skills (root of `skills/`):**
  `brainstorming`, `clean-code`, `code-reviewer`, `file-organizer`,
  `frontend-design`, `git-commit-helper`, `mcp-builder`, `mobile-design`,
  `react-best-practices`, `senior-architect`, `senior-backend`,
  `senior-frontend`, `senior-fullstack`, `senior-prompt-engineer`,
  `senior-security`, `ui-design-system`, `ui-ux-pro-max`.
- **Domain skill packs (`skills/<category>/<skill>/SKILL.md`):**
  - `apple/` (`apple-notes`, `apple-reminders`, `findmy`, `imessage`)
  - `autonomous-ai-agents/` (`antigravity-cli`, `blackbox`, `claude-code`,
    `codex`, `computer-use`, `grok`, `hermes-agent`, `opencode-cli`,
    `openhands`)
  - `blockchain/`, `communication/`, `creative/` (`architecture-diagram`,
    `ascii-video`, `auteur`, `baoyu-infographic`, `claude-design`,
    `concept-diagrams`, `excalidraw`, `humanizer`, `impeccable`, `manim-video`,
    `p5js`, `popular-web-designs`, `scrollcraft`, `sketch`, `system-atlas`,
    etc.)
  - `data-science/`, `devops/`, `dogfood/`, `email/`, `finance/`, `gaming/`,
    `health/`, `mcp/` (`fastmcp`, `mcp-oauth-remote-gateway`, `mcporter`),
    `media/`, `mlops/`, `note-taking/`, `payments/`, `productivity/` (`pdf`,
    `microsoft-office`, `google-workspace`, `maps`, etc.), `research/`
    (`arxiv`, `grounded-citations`, `llm-wiki`, `qmd`, etc.), `security/`
    (`domain-intel`, `osint-investigation`, `oss-forensics`, `web-pentest`),
    `smart-home/`, `social-media/`, `software-development/` (`ast-grep`,
    `codebase-inspection`, `github`, `requesting-code-review`, `simplify-code`,
    `spike`, `subagent-driven-development`, `systematic-debugging`,
    `test-driven-development`, etc.), `web/`, `web-development/`.
- **Claude Marketplace skills (`skills/claude-marketplace/`):**
  57 skills from official marketplace plugins (`build-mcp-server`,
  `build-mcp-app`, `build-mcpb`, `claude-automation-recommender`,
  `claude-md-improver`, `claude-security`, `playground`, `skill-creator`,
  `skill-development`, `agent-development`, `command-development`,
  `hook-development`, `mcp-integration`, `plugin-settings`, `plugin-structure`,
  `math-olympiad`, `siege`, `solo`, `receipts`, `session-report`,
  `project-artifact`, `champion-kit`, `claude-for-manufacturing`, etc.).

### 2. Agents (`agents/`, `.opencode/agents/`, and `~/.config/opencode/agents/`)

41 specialized subagents normalized to OpenCode V2 frontmatter (`description`
and `mode: subagent`):

- **Architecture & implementation:** `code-architect`, `code-explorer`,
  `architecture-critic`, `scaffolder`, `uplift-migrator`,
  `version-delta-analyst`, `legacy-analyst`, `business-rules-extractor`.
- **Review, quality & testing:** `code-reviewer`,
  `pr-review-toolkit-code-reviewer`, `code-simplifier`,
  `pr-review-toolkit-code-simplifier`, `silent-failure-hunter`,
  `comment-analyzer`, `pr-test-analyzer`, `type-design-analyzer`,
  `test-engineer`.
- **Security & auditing:** `security-auditor`, `claude-security`, `explore`,
  `scan-inventory`, `scan-loader`, `scan-redactor`, `scan-researcher`,
  `scan-verifier`, `patch-generator`, `patch-verifier`.
- **Plugin, skill & SDK tooling:** `agent-creator`, `skill-reviewer`,
  `plugin-validator`, `agent-sdk-verifier-py`, `agent-sdk-verifier-ts`,
  `conversation-analyzer`, `repo-scout`, `analyzer`, `comparator`, `grader`.
- **Formal & mathematical reasoning:** `math-proof-judge`,
  `math-proof-worker`, `math-proof-worker-deep`.

### 3. Plugins (`plugins/`)

- `plugins/pdfscrape.js` — OpenCode V2 tool plugin for `pdfscrape`.
- `plugins/hermes/` — 19 Hermes runtime plugins (`browser`, `computer_use`,
  `config_backends`, `context_engine`, `cron_providers`, `dashboard_auth`,
  `delegation`, `disk-cleanup`, `google_meet`, `hermes-achievements`,
  `image_gen`, `kanban`, `memory`, `model-providers`, `platforms`,
  `security-guidance`, `teams_pipeline`, `video_gen`, `web`).
- `plugins/claude-official/` — 42 Claude official marketplace plugin bundles
  (`agent-sdk-dev`, `champion-kit`, `claude-code-setup`,
  `claude-for-manufacturing`, `claude-md-management`, `claude-security`,
  `code-modernization`, `code-review`, `code-simplifier`, `commit-commands`,
  `feature-dev`, `frontend-design`, `hookify`, `math-olympiad`, `math-proof`,
  `mcp-server-dev`, `playground`, `plugin-dev`, `pr-review-toolkit`,
  `project-artifact`, `receipts`, `security-guidance`, `session-report`,
  `skill-creator`, LSP plugins, etc.).

## Testing

`tests/test_providers.py` shells out to the real CLIs and asserts that every
provider reports an auth state and, when signed out, explains why. A provider
that raises or omits its hint fails the suite. These tests need the CLIs on
`PATH`; they are the fastest way to catch a broken provider wiring.

`tests/test_cli.py` is pure logic and runs anywhere.

## Conventions

- Python 3.9 compatible. Use `from __future__ import annotations` for the
  `X | None` syntax.
- Line length 100, enforced by ruff (`E`, `F`, `I`, `UP`, `B`).
- Providers must not import from each other; shared helpers live in
  `providers/base.py`.
