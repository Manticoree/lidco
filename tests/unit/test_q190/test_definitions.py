"""Tests for DefinitionResolver — Q190, task 1063."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.lsp.definitions import (
    DefinitionResolver,
    Location,
    _file_uri,
    _parse_single_location,
    _parse_location_list,
    _dict_to_location,
)


class TestLocation(unittest.TestCase):
    def test_frozen(self):
        loc = Location(file="a.py", line=1, column=0)
        with self.assertRaises(AttributeError):
            loc.file = "b.py"  # type: ignore[misc]

    def test_defaults(self):
        loc = Location(file="a.py", line=5, column=3)
        self.assertEqual(loc.preview, "")

    def test_with_preview(self):
        loc = Location(file="a.py", line=5, column=3, preview="def foo():")
        self.assertEqual(loc.preview, "def foo():")

    def test_equality(self):
        a = Location(file="a.py", line=1, column=0)
        b = Location(file="a.py", line=1, column=0)
        self.assertEqual(a, b)


class TestDefinitionResolver(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.resolver = DefinitionResolver(self.client)

    def test_goto_definition_success(self):
        self.client.send_request.return_value = {
            "uri": "file:///src/foo.py",
            "range": {"start": {"line": 10, "character": 4}},
        }
        loc = self.resolver.goto_definition("src/foo.py", 5, 8)
        self.assertIsNotNone(loc)
        self.assertEqual(loc.line, 10)
        self.assertEqual(loc.column, 4)

    def test_goto_definition_list_result(self):
        self.client.send_request.return_value = [
            {"uri": "file:///a.py", "range": {"start": {"line": 1, "character": 0}}},
            {"uri": "file:///b.py", "range": {"start": {"line": 2, "character": 0}}},
        ]
        loc = self.resolver.goto_definition("test.py", 1, 0)
        self.assertIsNotNone(loc)
        self.assertIn("a.py", loc.file)

    def test_goto_definition_none_result(self):
        self.client.send_request.return_value = None
        loc = self.resolver.goto_definition("test.py", 1, 0)
        self.assertIsNone(loc)

    def test_goto_definition_empty_list(self):
        self.client.send_request.return_value = []
        loc = self.resolver.goto_definition("test.py", 1, 0)
        self.assertIsNone(loc)

    def test_goto_definition_runtime_error(self):
        self.client.send_request.side_effect = RuntimeError("not running")
        loc = self.resolver.goto_definition("test.py", 1, 0)
        self.assertIsNone(loc)

    def test_goto_definition_value_error(self):
        self.client.send_request.side_effect = ValueError("lsp error")
        loc = self.resolver.goto_definition("test.py", 1, 0)
        self.assertIsNone(loc)

    def test_goto_type_definition_success(self):
        self.client.send_request.return_value = {
            "uri": "file:///types.py",
            "range": {"start": {"line": 20, "character": 0}},
        }
        loc = self.resolver.goto_type_definition("test.py", 5, 3)
        self.assertIsNotNone(loc)
        self.assertEqual(loc.line, 20)

    def test_goto_type_definition_none(self):
        self.client.send_request.return_value = None
        loc = self.resolver.goto_type_definition("test.py", 1, 0)
        self.assertIsNone(loc)

    def test_goto_implementation_success(self):
        self.client.send_request.return_value = [
            {"uri": "file:///impl1.py", "range": {"start": {"line": 5, "character": 0}}},
            {"uri": "file:///impl2.py", "range": {"start": {"line": 10, "character": 0}}},
        ]
        locs = self.resolver.goto_implementation("base.py", 3, 6)
        self.assertEqual(len(locs), 2)

    def test_goto_implementation_empty(self):
        self.client.send_request.return_value = []
        locs = self.resolver.goto_implementation("base.py", 3, 6)
        self.assertEqual(locs, [])

    def test_goto_implementation_error(self):
        self.client.send_request.side_effect = RuntimeError("fail")
        locs = self.resolver.goto_implementation("base.py", 3, 6)
        self.assertEqual(locs, [])

    def test_sends_correct_params(self):
        self.client.send_request.return_value = None
        self.resolver.goto_definition("foo.py", 10, 5)
        self.client.send_request.assert_called_once_with(
            "textDocument/definition",
            {
                "textDocument": {"uri": _file_uri("foo.py")},
                "position": {"line": 10, "character": 5},
            },
        )


class TestFileUri(unittest.TestCase):
    def test_unix_path(self):
        self.assertEqual(_file_uri("/home/user/file.py"), "file:///home/user/file.py")

    def test_relative_path(self):
        result = _file_uri("src/foo.py")
        self.assertTrue(result.startswith("file:///"))

    def test_windows_backslash(self):
        result = _file_uri("C:\\Users\\file.py")
        self.assertNotIn("\\", result)


class TestParseHelpers(unittest.TestCase):
    def test_parse_single_location_none(self):
        self.assertIsNone(_parse_single_location(None))

    def test_parse_single_location_dict(self):
        loc = _parse_single_location({
            "uri": "file:///a.py",
            "range": {"start": {"line": 1, "character": 2}},
        })
        self.assertIsNotNone(loc)
        self.assertEqual(loc.line, 1)

    def test_parse_location_list_empty(self):
        self.assertEqual(_parse_location_list([]), [])

    def test_parse_location_list_dict(self):
        result = _parse_location_list({
            "uri": "file:///a.py",
            "range": {"start": {"line": 0, "character": 0}},
        })
        self.assertEqual(len(result), 1)

    def test_dict_to_location_empty(self):
        loc = _dict_to_location({})
        # Empty dict produces a Location with all defaults
        self.assertIsNotNone(loc)
        self.assertEqual(loc.file, "")
        self.assertEqual(loc.line, 0)

    def test_dict_to_location_bad_type(self):
        # Non-dict-like input triggers exception path
        self.assertIsNone(_dict_to_location(None))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
