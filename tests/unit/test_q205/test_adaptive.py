"""Tests for lidco.terminal.adaptive."""

from __future__ import annotations

from unittest.mock import MagicMock

from lidco.terminal.adaptive import AdaptiveRenderer
from lidco.terminal.detector import TerminalCapabilities, TerminalDetector, TerminalType


def _make_renderer(caps: TerminalCapabilities) -> AdaptiveRenderer:
    """Build an AdaptiveRenderer with specific capabilities."""
    det = MagicMock(spec=TerminalDetector)
    det.capabilities.return_value = caps
    return AdaptiveRenderer(detector=det)


class TestAdaptiveRenderer:
    def test_render_text_plain_no_color(self):
        r = _make_renderer(TerminalCapabilities())
        assert r.render_text("hello", bold=True, color="red") == "hello"

    def test_render_text_bold(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        out = r.render_text("hi", bold=True)
        assert "\033[1m" in out
        assert "hi" in out
        assert "\033[0m" in out

    def test_render_text_color(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        out = r.render_text("hi", color="red")
        assert "\033[31m" in out

    def test_render_text_bold_and_color(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        out = r.render_text("hi", bold=True, color="green")
        assert "\033[1;32m" in out

    def test_render_text_unknown_color_no_codes(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        out = r.render_text("hi", color="neon")
        assert out == "hi"

    def test_render_link_with_hyperlinks(self):
        r = _make_renderer(TerminalCapabilities(hyperlinks=True))
        out = r.render_link("https://example.com", "Example")
        assert "Example" in out
        assert "https://example.com" in out
        assert "\033]8;;" in out

    def test_render_link_without_hyperlinks(self):
        r = _make_renderer(TerminalCapabilities())
        out = r.render_link("https://example.com", "Example")
        assert out == "Example"

    def test_render_link_no_label(self):
        r = _make_renderer(TerminalCapabilities())
        out = r.render_link("https://example.com")
        assert out == "https://example.com"

    def test_render_progress_unicode(self):
        r = _make_renderer(TerminalCapabilities(unicode=True))
        out = r.render_progress(0.5, width=10)
        assert "\u2588" in out
        assert "50%" in out

    def test_render_progress_ascii(self):
        r = _make_renderer(TerminalCapabilities())
        out = r.render_progress(1.0, width=10)
        assert "#" in out
        assert "100%" in out

    def test_render_progress_clamps(self):
        r = _make_renderer(TerminalCapabilities())
        out = r.render_progress(-0.5, width=10)
        assert "0%" in out
        out2 = r.render_progress(2.0, width=10)
        assert "100%" in out2

    def test_supports_color(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        assert r.supports_color() is True

    def test_supports_unicode(self):
        r = _make_renderer(TerminalCapabilities(unicode=True))
        assert r.supports_unicode() is True

    def test_fallback_mode_true(self):
        r = _make_renderer(TerminalCapabilities())
        assert r.fallback_mode() is True

    def test_fallback_mode_false(self):
        r = _make_renderer(TerminalCapabilities(color_256=True))
        assert r.fallback_mode() is False
