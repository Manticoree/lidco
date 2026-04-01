"""Tests for lidco.pairing.completion_provider."""

from __future__ import annotations

import unittest

from lidco.pairing.completion_provider import CompletionItem, CompletionProvider


class TestCompletionItem(unittest.TestCase):
    def test_frozen(self) -> None:
        item = CompletionItem(label="x", insert_text="x")
        with self.assertRaises(AttributeError):
            item.label = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        item = CompletionItem(label="x", insert_text="x")
        assert item.kind == "text"
        assert item.detail == ""
        assert item.sort_priority == 50


class TestCompletionProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = CompletionProvider()

    def test_add_symbols_and_count(self) -> None:
        self.provider.add_symbols([
            {"name": "MyClass", "kind": "class", "module": "app"},
            {"name": "my_func", "kind": "function", "module": "utils"},
        ])
        assert self.provider.symbol_count() == 2

    def test_complete_prefix_user_symbols(self) -> None:
        self.provider.add_symbols([
            {"name": "calculate_total", "kind": "function", "module": "math_utils"},
        ])
        items = self.provider.complete("calc")
        assert len(items) >= 1
        assert any(i.label == "calculate_total" for i in items)

    def test_complete_prefix_builtins(self) -> None:
        items = self.provider.complete("pri")
        assert any(i.label == "print" for i in items)

    def test_complete_empty_prefix(self) -> None:
        items = self.provider.complete("")
        assert items == []

    def test_complete_max_items(self) -> None:
        items = self.provider.complete("s", max_items=3)
        assert len(items) <= 3

    def test_complete_import(self) -> None:
        items = self.provider.complete_import("js")
        assert any(i.label == "json" for i in items)
        assert all("import" in i.insert_text for i in items)

    def test_complete_attribute_str(self) -> None:
        items = self.provider.complete_attribute("str")
        labels = [i.label for i in items]
        assert "upper" in labels
        assert "lower" in labels
        assert "strip" in labels

    def test_complete_attribute_with_prefix(self) -> None:
        items = self.provider.complete_attribute("list", "app")
        assert len(items) == 1
        assert items[0].label == "append"

    def test_complete_attribute_unknown_type(self) -> None:
        items = self.provider.complete_attribute("unknown_type")
        assert items == []

    def test_clear_symbols(self) -> None:
        self.provider.add_symbols([{"name": "x", "kind": "var", "module": "m"}])
        assert self.provider.symbol_count() == 1
        self.provider.clear_symbols()
        assert self.provider.symbol_count() == 0

    def test_sort_priority(self) -> None:
        self.provider.add_symbols([
            {"name": "sorted_data", "kind": "variable", "module": "app"},
        ])
        items = self.provider.complete("sorted")
        # User symbol (priority 10) should come before builtin (priority 30)
        if len(items) >= 2:
            assert items[0].sort_priority <= items[1].sort_priority


if __name__ == "__main__":
    unittest.main()
