"""Tests for lidco.terminal.render_engine."""

from __future__ import annotations

from lidco.terminal.render_engine import RenderBuffer, RenderEngine, RenderMode


class TestRenderBuffer:
    def test_write_appends_line(self):
        buf = RenderBuffer()
        buf.write("hello")
        assert buf.lines == ["hello"]
        assert buf.dirty is True

    def test_clear_removes_all_lines(self):
        buf = RenderBuffer(lines=["a", "b"])
        buf.clear()
        assert buf.lines == []
        assert buf.dirty is True

    def test_render_joins_lines(self):
        buf = RenderBuffer(lines=["line1", "line2", "line3"])
        assert buf.render() == "line1\nline2\nline3"

    def test_diff_identical_buffers(self):
        a = RenderBuffer(lines=["x", "y"])
        b = RenderBuffer(lines=["x", "y"])
        assert a.diff(b) == []

    def test_diff_changed_lines(self):
        a = RenderBuffer(lines=["x", "y", "z"])
        b = RenderBuffer(lines=["x", "CHANGED", "z"])
        assert a.diff(b) == [1]

    def test_diff_different_lengths(self):
        a = RenderBuffer(lines=["x"])
        b = RenderBuffer(lines=["x", "y"])
        assert a.diff(b) == [1]


class TestRenderEngine:
    def test_write_and_flush(self):
        engine = RenderEngine()
        engine.write("hello\nworld")
        output = engine.flush()
        assert output == "hello\nworld"
        assert engine.buffer.dirty is False

    def test_clear(self):
        engine = RenderEngine()
        engine.write("test")
        engine.clear()
        assert engine.line_count() == 0

    def test_resize(self):
        engine = RenderEngine()
        engine.resize(120, 40)
        assert engine.buffer.width == 120
        assert engine.buffer.height == 40

    def test_set_mode(self):
        engine = RenderEngine(mode=RenderMode.NORMAL)
        engine.set_mode(RenderMode.ALT_SCREEN)
        assert engine._mode == RenderMode.ALT_SCREEN

    def test_line_count(self):
        engine = RenderEngine()
        engine.write("a\nb\nc")
        assert engine.line_count() == 3

    def test_buffer_property(self):
        engine = RenderEngine(width=100, height=50)
        assert engine.buffer.width == 100
        assert engine.buffer.height == 50

    def test_modes_enum_values(self):
        assert RenderMode.NORMAL.value == "normal"
        assert RenderMode.ALT_SCREEN.value == "alt_screen"
        assert RenderMode.MINIMAL.value == "minimal"

    def test_flush_marks_clean(self):
        engine = RenderEngine()
        engine.write("data")
        assert engine.buffer.dirty is True
        engine.flush()
        assert engine.buffer.dirty is False
