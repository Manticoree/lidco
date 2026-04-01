"""Tests for ReferenceFinder — Q190, task 1064."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.lsp.references import (
    ReferenceFinder,
    Reference,
    SymbolInfo,
    CallNode,
    _parse_references,
    _parse_symbols,
    _item_to_call_node,
)


class TestReference(unittest.TestCase):
    def test_frozen(self):
        r = Reference(file="a.py", line=1, column=0)
        with self.assertRaises(AttributeError):
            r.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        r = Reference(file="a.py", line=1, column=0)
        self.assertFalse(r.is_declaration)
        self.assertEqual(r.preview, "")


class TestSymbolInfo(unittest.TestCase):
    def test_frozen(self):
        s = SymbolInfo(name="Foo", kind=5, file="a.py", line=1)
        with self.assertRaises(AttributeError):
            s.name = "Bar"  # type: ignore[misc]

    def test_defaults(self):
        s = SymbolInfo(name="Foo", kind=5, file="a.py", line=1)
        self.assertEqual(s.column, 0)
        self.assertEqual(s.container_name, "")


class TestCallNode(unittest.TestCase):
    def test_frozen(self):
        n = CallNode(name="foo", file="a.py", line=1)
        with self.assertRaises(AttributeError):
            n.name = "bar"  # type: ignore[misc]

    def test_children_default(self):
        n = CallNode(name="foo", file="a.py", line=1)
        self.assertEqual(n.children, ())

    def test_with_children(self):
        child = CallNode(name="bar", file="b.py", line=5)
        parent = CallNode(name="foo", file="a.py", line=1, children=(child,))
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(parent.children[0].name, "bar")


class TestReferenceFinder(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.finder = ReferenceFinder(self.client)

    def test_find_references_success(self):
        self.client.send_request.return_value = [
            {"uri": "file:///a.py", "range": {"start": {"line": 1, "character": 0}}},
            {"uri": "file:///b.py", "range": {"start": {"line": 5, "character": 3}}},
        ]
        refs = self.finder.find_references("test.py", 10, 5)
        self.assertEqual(len(refs), 2)
        self.assertIsInstance(refs, tuple)

    def test_find_references_empty(self):
        self.client.send_request.return_value = []
        refs = self.finder.find_references("test.py", 1, 0)
        self.assertEqual(refs, ())

    def test_find_references_error(self):
        self.client.send_request.side_effect = RuntimeError("not running")
        refs = self.finder.find_references("test.py", 1, 0)
        self.assertEqual(refs, ())

    def test_find_references_include_declaration(self):
        self.client.send_request.return_value = [
            {"uri": "file:///a.py", "range": {"start": {"line": 1, "character": 0}}},
        ]
        self.finder.find_references("test.py", 1, 0, include_declaration=True)
        call_args = self.client.send_request.call_args
        self.assertTrue(call_args[0][1]["context"]["includeDeclaration"])

    def test_find_workspace_symbols_success(self):
        self.client.send_request.return_value = [
            {
                "name": "MyClass",
                "kind": 5,
                "location": {
                    "uri": "file:///mod.py",
                    "range": {"start": {"line": 10, "character": 0}},
                },
                "containerName": "module",
            },
        ]
        symbols = self.finder.find_workspace_symbols("MyClass")
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0].name, "MyClass")
        self.assertEqual(symbols[0].container_name, "module")

    def test_find_workspace_symbols_empty(self):
        self.client.send_request.return_value = []
        symbols = self.finder.find_workspace_symbols("nothing")
        self.assertEqual(symbols, ())

    def test_find_workspace_symbols_error(self):
        self.client.send_request.side_effect = ValueError("error")
        symbols = self.finder.find_workspace_symbols("test")
        self.assertEqual(symbols, ())

    def test_call_hierarchy_success(self):
        self.client.send_request.side_effect = [
            # prepareCallHierarchy
            [{"name": "foo", "uri": "file:///a.py", "range": {"start": {"line": 5, "character": 0}}}],
            # incomingCalls
            [{"from": {"name": "bar", "uri": "file:///b.py", "range": {"start": {"line": 10, "character": 0}}}}],
        ]
        node = self.finder.call_hierarchy("a.py", 5, 0)
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "foo")
        self.assertEqual(len(node.children), 1)
        self.assertEqual(node.children[0].name, "bar")

    def test_call_hierarchy_none_result(self):
        self.client.send_request.return_value = None
        node = self.finder.call_hierarchy("a.py", 5, 0)
        self.assertIsNone(node)

    def test_call_hierarchy_empty_list(self):
        self.client.send_request.return_value = []
        node = self.finder.call_hierarchy("a.py", 5, 0)
        self.assertIsNone(node)

    def test_call_hierarchy_error(self):
        self.client.send_request.side_effect = RuntimeError("fail")
        node = self.finder.call_hierarchy("a.py", 5, 0)
        self.assertIsNone(node)


class TestParseReferences(unittest.TestCase):
    def test_none_input(self):
        self.assertEqual(_parse_references(None, False), ())

    def test_non_list_input(self):
        self.assertEqual(_parse_references("invalid", False), ())

    def test_valid_refs(self):
        refs = _parse_references([
            {"uri": "file:///a.py", "range": {"start": {"line": 1, "character": 2}}},
        ], False)
        self.assertEqual(len(refs), 1)

    def test_skips_non_dict_items(self):
        refs = _parse_references([None, "bad", {"uri": "file:///a.py", "range": {"start": {"line": 0, "character": 0}}}], False)
        self.assertEqual(len(refs), 1)


class TestParseSymbols(unittest.TestCase):
    def test_none_input(self):
        self.assertEqual(_parse_symbols(None), ())

    def test_valid_symbols(self):
        syms = _parse_symbols([
            {
                "name": "X",
                "kind": 5,
                "location": {"uri": "file:///a.py", "range": {"start": {"line": 0, "character": 0}}},
            },
        ])
        self.assertEqual(len(syms), 1)
        self.assertEqual(syms[0].name, "X")


class TestItemToCallNode(unittest.TestCase):
    def test_basic(self):
        node = _item_to_call_node({
            "name": "foo",
            "uri": "file:///a.py",
            "range": {"start": {"line": 5, "character": 2}},
        })
        self.assertEqual(node.name, "foo")
        self.assertEqual(node.line, 5)

    def test_fallback_selection_range(self):
        node = _item_to_call_node({
            "name": "bar",
            "uri": "file:///b.py",
            "selectionRange": {"start": {"line": 10, "character": 0}},
        })
        self.assertEqual(node.line, 10)


if __name__ == "__main__":
    unittest.main()
