"""Tests for keyboard shortcut helpers — Task 151."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from lidco.cli.app import _run_shortcut, BANNER


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_event(buffer_text: str = "") -> MagicMock:
    """Return a mock prompt_toolkit key event with a mock Buffer."""
    buf = MagicMock()
    buf.text = buffer_text
    event = MagicMock()
    event.current_buffer = buf
    return event


# ── _run_shortcut (require_empty=True) ───────────────────────────────────────

class TestRunShortcutRequireEmpty:
    """Shortcuts that only fire when the buffer is empty."""

    def test_empty_buffer_resets_and_inserts(self) -> None:
        event = _make_event("")
        _run_shortcut(event, "/retry")
        event.current_buffer.reset.assert_called_once()
        event.current_buffer.insert_text.assert_called_once_with("/retry")
        event.current_buffer.validate_and_handle.assert_called_once()

    def test_whitespace_only_buffer_treated_as_empty(self) -> None:
        event = _make_event("   ")
        _run_shortcut(event, "/retry")
        event.current_buffer.reset.assert_called_once()
        event.current_buffer.validate_and_handle.assert_called_once()

    def test_nonempty_buffer_does_nothing(self) -> None:
        event = _make_event("some text")
        _run_shortcut(event, "/retry")
        event.current_buffer.reset.assert_not_called()
        event.current_buffer.insert_text.assert_not_called()
        event.current_buffer.validate_and_handle.assert_not_called()

    def test_partial_command_in_buffer_does_nothing(self) -> None:
        event = _make_event("/cl")
        _run_shortcut(event, "/clear")
        event.current_buffer.reset.assert_not_called()

    def test_inserts_correct_command(self) -> None:
        for cmd in ("/clear", "/retry", "/export", "/status"):
            event = _make_event("")
            _run_shortcut(event, cmd)
            event.current_buffer.insert_text.assert_called_with(cmd)

    def test_default_require_empty_is_true(self) -> None:
        """Default behaviour must be require_empty=True to protect editing."""
        import inspect
        sig = inspect.signature(_run_shortcut)
        assert sig.parameters["require_empty"].default is True


# ── _run_shortcut (require_empty=False) ──────────────────────────────────────

class TestRunShortcutAlways:
    """Ctrl+L always clears regardless of buffer content."""

    def test_fires_when_buffer_empty(self) -> None:
        event = _make_event("")
        _run_shortcut(event, "/clear", require_empty=False)
        event.current_buffer.reset.assert_called_once()
        event.current_buffer.validate_and_handle.assert_called_once()

    def test_fires_when_buffer_has_text(self) -> None:
        event = _make_event("some typed text")
        _run_shortcut(event, "/clear", require_empty=False)
        event.current_buffer.reset.assert_called_once()
        event.current_buffer.insert_text.assert_called_once_with("/clear")
        event.current_buffer.validate_and_handle.assert_called_once()

    def test_fires_with_multiline_content(self) -> None:
        event = _make_event("line1\nline2\nline3")
        _run_shortcut(event, "/clear", require_empty=False)
        event.current_buffer.reset.assert_called_once()


# ── SHORTCUTS registry ────────────────────────────────────────────────────────

class TestShortcutsRegistry:
    """SHORTCUTS list used by the future /shortcuts command."""

    def _get_shortcuts(self) -> list:
        # Import from inside run_repl is not possible, so we test that
        # the attribute can be found once the module is imported.
        # The SHORTCUTS list is defined inside run_repl; here we verify
        # _run_shortcut (the helper) is exported at module level.
        from lidco.cli import app
        return getattr(app, "SHORTCUTS", None)

    def test_shortcuts_not_module_level_yet(self) -> None:
        """SHORTCUTS is defined inside run_repl; _run_shortcut IS module-level."""
        from lidco.cli import app
        # _run_shortcut must be accessible for unit testing
        assert callable(app._run_shortcut)

    def test_banner_exists(self) -> None:
        assert "LIDCO" in BANNER

    def test_run_shortcut_order_of_operations(self) -> None:
        """reset() must be called before insert_text() to avoid appending."""
        calls_log: list[str] = []
        event = _make_event("")
        event.current_buffer.reset.side_effect = lambda: calls_log.append("reset")
        event.current_buffer.insert_text.side_effect = lambda _: calls_log.append("insert")
        event.current_buffer.validate_and_handle.side_effect = lambda: calls_log.append("submit")

        _run_shortcut(event, "/export", require_empty=False)

        assert calls_log == ["reset", "insert", "submit"]
