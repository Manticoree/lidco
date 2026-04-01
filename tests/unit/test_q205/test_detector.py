"""Tests for lidco.terminal.detector."""

from __future__ import annotations

from unittest.mock import patch

from lidco.terminal.detector import (
    TerminalCapabilities,
    TerminalDetector,
    TerminalType,
)


class TestTerminalDetector:
    def test_detect_iterm2(self):
        with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.ITERM2

    def test_detect_wezterm(self):
        with patch.dict("os.environ", {"TERM_PROGRAM": "WezTerm"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.WEZTERM

    def test_detect_kitty(self):
        with patch.dict("os.environ", {"KITTY_WINDOW_ID": "1"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.KITTY

    def test_detect_ghostty(self):
        with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.GHOSTTY

    def test_detect_windows_terminal(self):
        with patch.dict("os.environ", {"WT_SESSION": "abc-123"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.WINDOWS_TERMINAL

    def test_detect_xterm(self):
        with patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.XTERM

    def test_detect_unknown(self):
        with patch.dict("os.environ", {}, clear=True):
            d = TerminalDetector()
            assert d.detect() == TerminalType.UNKNOWN

    def test_capabilities_iterm2(self):
        d = TerminalDetector()
        caps = d.capabilities(TerminalType.ITERM2)
        assert caps.truecolor is True
        assert caps.images is True
        assert caps.hyperlinks is True

    def test_capabilities_unknown(self):
        d = TerminalDetector()
        caps = d.capabilities(TerminalType.UNKNOWN)
        assert caps.color_256 is False
        assert caps.truecolor is False

    def test_is_interactive_true(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            d = TerminalDetector()
            assert d.is_interactive() is True

    def test_is_interactive_false(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            d = TerminalDetector()
            assert d.is_interactive() is False

    def test_terminal_size_default_fallback(self):
        with patch("os.get_terminal_size", side_effect=OSError):
            d = TerminalDetector()
            assert d.terminal_size() == (80, 24)

    def test_summary_contains_terminal(self):
        with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app"}, clear=True):
            with patch("os.get_terminal_size", side_effect=OSError):
                d = TerminalDetector()
                s = d.summary()
                assert "iterm2" in s
                assert "Size:" in s
