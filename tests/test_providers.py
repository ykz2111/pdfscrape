"""Tests that every provider is reachable and reports auth state.

These shell out to the local CLIs, so they are skipped when a CLI is missing.
"""

import pytest

from pdfscrape.providers import all_providers


@pytest.mark.parametrize("provider", all_providers(), ids=lambda p: p.name)
def test_provider_reports_auth(provider):
    status = provider.auth()
    assert isinstance(status.logged_in, bool)
    if not status.logged_in:
        assert status.detail, "a failed provider must explain why"
        assert status.login_hint, "a failed provider must say how to fix it"


def test_codex_model_catalog_is_chatgpt_compatible():
    from pdfscrape.providers.codex import CHATGPT_MODELS

    assert "gpt-6.1-sol" in CHATGPT_MODELS
    assert not any(m.startswith("codex-") for m in CHATGPT_MODELS), (
        "codex-* aliases are rejected for ChatGPT accounts"
    )
