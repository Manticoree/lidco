"""Tests for Q273 Widget framework — Widget, WidgetManager, focus, events."""
from __future__ import annotations

import unittest

from lidco.widgets.framework import Widget, WidgetEvent, WidgetManager


class TestWidgetEvent(unittest.TestCase):
    def test_event_creation(self):
        e = WidgetEvent(type="click", target="btn1")
        assert e.type == "click"
        assert e.target == "btn1"
        assert e.data == {}
        assert e.timestamp > 0

    def test_event_frozen(self):
        e = WidgetEvent(type="focus", target="w1")
        with self.assertRaises(AttributeError):
            e.type = "blur"  # type: ignore[misc]


class TestWidget(unittest.TestCase):
    def test_defaults(self):
        w = Widget(id="w1")
        assert w.id == "w1"
        assert w.title == ""
        assert w.is_visible()
        assert w.focusable
        assert not w.is_focused()

    def test_focus_blur(self):
        w = Widget(id="w1")
        w.focus()
        assert w.is_focused()
        w.blur()
        assert not w.is_focused()

    def test_show_hide(self):
        w = Widget(id="w1")
        w.hide()
        assert not w.is_visible()
        w.show()
        assert w.is_visible()

    def test_render_returns_title(self):
        w = Widget(id="w1", title="My Widget")
        assert w.render() == "My Widget"

    def test_handle_focus_event(self):
        w = Widget(id="w1")
        e = WidgetEvent(type="focus", target="w1")
        assert w.handle_event(e) is True
        assert w.is_focused()

    def test_handle_blur_event(self):
        w = Widget(id="w1")
        w.focus()
        e = WidgetEvent(type="blur", target="w1")
        assert w.handle_event(e) is True
        assert not w.is_focused()

    def test_handle_unrelated_event(self):
        w = Widget(id="w1")
        e = WidgetEvent(type="click", target="w1")
        assert w.handle_event(e) is False


class TestWidgetManager(unittest.TestCase):
    def test_add_and_get(self):
        mgr = WidgetManager()
        w = Widget(id="w1", title="A")
        mgr.add(w)
        assert mgr.get("w1") is w
        assert mgr.get("nope") is None

    def test_remove(self):
        mgr = WidgetManager()
        mgr.add(Widget(id="w1"))
        assert mgr.remove("w1") is True
        assert mgr.get("w1") is None
        assert mgr.remove("w1") is False

    def test_focus_next_cycles(self):
        mgr = WidgetManager()
        mgr.add(Widget(id="a"))
        mgr.add(Widget(id="b"))
        mgr.add(Widget(id="c"))
        first = mgr.focus_next()
        assert first is not None
        assert first.id == "a"
        second = mgr.focus_next()
        assert second is not None
        assert second.id == "b"

    def test_focus_next_skips_hidden(self):
        mgr = WidgetManager()
        w1 = Widget(id="a")
        w2 = Widget(id="b")
        w1.hide()
        mgr.add(w1)
        mgr.add(w2)
        got = mgr.focus_next()
        assert got is not None
        assert got.id == "b"

    def test_focused_none_initially(self):
        mgr = WidgetManager()
        assert mgr.focused() is None

    def test_render_all_visible(self):
        mgr = WidgetManager()
        mgr.add(Widget(id="a", title="AAA"))
        w2 = Widget(id="b", title="BBB")
        w2.hide()
        mgr.add(w2)
        mgr.add(Widget(id="c", title="CCC"))
        rendered = mgr.render_all()
        assert "AAA" in rendered
        assert "BBB" not in rendered
        assert "CCC" in rendered

    def test_dispatch_to_target(self):
        mgr = WidgetManager()
        w = Widget(id="w1")
        mgr.add(w)
        e = WidgetEvent(type="focus", target="w1")
        assert mgr.dispatch(e) is True
        assert w.is_focused()

    def test_all_widgets(self):
        mgr = WidgetManager()
        mgr.add(Widget(id="a"))
        mgr.add(Widget(id="b"))
        assert len(mgr.all_widgets()) == 2

    def test_summary(self):
        mgr = WidgetManager()
        mgr.add(Widget(id="a"))
        w2 = Widget(id="b")
        w2.hide()
        mgr.add(w2)
        s = mgr.summary()
        assert s["total"] == 2
        assert s["visible"] == 1
        assert s["focused"] is None


if __name__ == "__main__":
    unittest.main()
