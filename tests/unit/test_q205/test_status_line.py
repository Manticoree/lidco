"""Tests for lidco.terminal.status_line."""

from __future__ import annotations

from lidco.terminal.status_line import StatusItem, StatusLine


class TestStatusItem:
    def test_frozen(self):
        item = StatusItem(key="k", value="v")
        assert item.priority == 50
        try:
            item.key = "other"  # type: ignore[misc]
            assert False, "Expected FrozenInstanceError"
        except AttributeError:
            pass


class TestStatusLine:
    def test_set_and_get(self):
        sl = StatusLine()
        sl.set("model", "gpt-4")
        assert sl.get("model") == "gpt-4"

    def test_get_missing(self):
        sl = StatusLine()
        assert sl.get("nope") is None

    def test_remove_existing(self):
        sl = StatusLine()
        sl.set("k", "v")
        assert sl.remove("k") is True
        assert sl.get("k") is None

    def test_remove_missing(self):
        sl = StatusLine()
        assert sl.remove("nope") is False

    def test_render_sorted_by_priority(self):
        sl = StatusLine()
        sl.set("low", "1", priority=100)
        sl.set("high", "2", priority=10)
        rendered = sl.render()
        assert rendered.index("high") < rendered.index("low")

    def test_render_custom_separator(self):
        sl = StatusLine()
        sl.set("a", "1")
        sl.set("b", "2")
        rendered = sl.render(separator=" -- ")
        assert " -- " in rendered

    def test_clear(self):
        sl = StatusLine()
        sl.set("a", "1")
        sl.clear()
        assert sl.item_count() == 0

    def test_item_count(self):
        sl = StatusLine()
        assert sl.item_count() == 0
        sl.set("a", "1")
        sl.set("b", "2")
        assert sl.item_count() == 2

    def test_set_model(self):
        sl = StatusLine()
        sl.set_model("claude-opus")
        assert sl.get("model") == "claude-opus"

    def test_set_mode(self):
        sl = StatusLine()
        sl.set_mode("turbo")
        assert sl.get("mode") == "turbo"

    def test_set_tokens(self):
        sl = StatusLine()
        sl.set_tokens(1500, 200000)
        assert sl.get("tokens") == "1500/200000"

    def test_convenience_priority_order(self):
        sl = StatusLine()
        sl.set_tokens(100, 1000)
        sl.set_mode("fast")
        sl.set_model("gpt-4")
        rendered = sl.render()
        # model (10) < mode (20) < tokens (30)
        assert rendered.index("model:") < rendered.index("mode:") < rendered.index("tokens:")
