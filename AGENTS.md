# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

`pdfscrape` is a CLI that routes prompts to several AI providers. It is a thin
orchestration layer: **it never holds an API key**. Each provider shells out to
a CLI that already carries the user's OAuth session.

## Non-negotiable design rule

Do not add API-key handling, `.env` loading of provider tokens, or new
provider endpoints that require a pasted secret. If a provider needs
credentials, it must reuse an existing signed-in CLI or a token already in the
OS keychain.

Adding a provider means adding a module under `pdfscrape/providers/` that
implements `auth()` and `run()`, then registering it in `_FACTORIES` in
`pdfscrape/providers/__init__.py`. Also add it to `provider_names()` so
`pdfscrape init` reports it.

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
