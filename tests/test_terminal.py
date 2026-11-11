"""Tests for the macOS terminal interface."""

from pdfscrape.terminal import COMMANDS, Style, TerminalChat, colour_enabled


def test_colour_disabled_without_tty():
    """Colour must be off when stdout is not a terminal."""
    assert colour_enabled(stream=object()) is False


def test_colour_honours_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert colour_enabled() is False


def test_style_is_identity_when_disabled():
    style = Style(enabled=False)
    assert style("hello", "red", "bold") == "hello"


def test_style_wraps_when_enabled():
    style = Style(enabled=True)
    output = style("hello", "red")
    assert "hello" in output
    assert output != "hello"
    assert output.endswith("\033[0m")


def test_commands_cover_the_documented_set():
    for command in ("/help", "/status", "/providers", "/login", "/use",
                    "/model", "/clear", "/history", "/quit"):
        assert command in COMMANDS


def test_unknown_command_is_reported():
    chat = TerminalChat(style=Style(enabled=False))
    errors = []
    chat.error = errors.append

    assert chat.handle_command("/nope") is True
    assert errors and "nope" in errors[0]


def test_quit_ends_the_session():
    chat = TerminalChat(style=Style(enabled=False))
    assert chat.handle_command("/quit") is False
    assert chat.handle_command("/exit") is False


def test_use_rejects_unknown_provider():
    chat = TerminalChat(style=Style(enabled=False))
    errors = []
    chat.error = errors.append

    chat.handle_command("/use notaprovider")
    assert errors
    assert chat.provider != "notaprovider"


def test_use_accepts_auto_and_known_providers():
    chat = TerminalChat(style=Style(enabled=False))

    chat.handle_command("/use copilot")
    assert chat.provider == "copilot"

    chat.handle_command("/use auto")
    assert chat.provider == "auto"


def test_model_command_requires_a_provider():
    chat = TerminalChat(style=Style(enabled=False))
    errors = []
    chat.error = errors.append

    chat.handle_command("/model")
    assert errors


def test_login_lists_hints_for_every_provider():
    from pdfscrape.providers import provider_names
    from pdfscrape.terminal import LOGIN_HINTS

    for name in provider_names():
        assert name in LOGIN_HINTS
        assert LOGIN_HINTS[name]


def test_history_records_prompts():
    chat = TerminalChat(style=Style(enabled=False))
    chat.history.append("first")
    chat.history.append("second")
    assert chat.history == ["first", "second"]
