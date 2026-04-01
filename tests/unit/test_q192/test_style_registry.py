"""Tests for StyleRegistry, DefaultStyle, BriefStyle — task 1072."""
from __future__ import annotations

import unittest

from lidco.output.style_registry import (
    BriefStyle,
    DefaultStyle,
    OutputStyle,
    StyleRegistry,
)


class TestOutputStyleProtocol(unittest.TestCase):
    def test_default_is_output_style(self):
        self.assertIsInstance(DefaultStyle(), OutputStyle)

    def test_brief_is_output_style(self):
        self.assertIsInstance(BriefStyle(), OutputStyle)


class TestDefaultStyle(unittest.TestCase):
    def test_name(self):
        self.assertEqual(DefaultStyle().name, "default")

    def test_transform_passthrough(self):
        self.assertEqual(DefaultStyle().transform("hello"), "hello")

    def test_wrap_response_passthrough(self):
        self.assertEqual(DefaultStyle().wrap_response("resp"), "resp")

    def test_transform_empty(self):
        self.assertEqual(DefaultStyle().transform(""), "")


class TestBriefStyle(unittest.TestCase):
    def test_name(self):
        self.assertEqual(BriefStyle().name, "brief")

    def test_transform_strips_blank_lines(self):
        text = "line1\n\n\nline2\n\nline3"
        result = BriefStyle().transform(text)
        self.assertEqual(result, "line1\nline2\nline3")

    def test_wrap_response_truncates(self):
        lines = "\n".join(f"line{i}" for i in range(20))
        result = BriefStyle().wrap_response(lines)
        self.assertIn("... (truncated)", result)
        self.assertEqual(len(result.splitlines()), 11)

    def test_wrap_response_short(self):
        result = BriefStyle().wrap_response("short")
        self.assertEqual(result, "short")

    def test_transform_preserves_content_lines(self):
        result = BriefStyle().transform("a\nb\nc")
        self.assertEqual(result, "a\nb\nc")


class TestStyleRegistryInit(unittest.TestCase):
    def test_empty_registry(self):
        r = StyleRegistry()
        self.assertEqual(r.list_styles(), ())
        self.assertIsNone(r.active)

    def test_registry_with_styles(self):
        r = StyleRegistry((DefaultStyle(), BriefStyle()))
        self.assertIn("default", r.list_styles())
        self.assertIn("brief", r.list_styles())


class TestStyleRegistryRegister(unittest.TestCase):
    def test_register_returns_new(self):
        r1 = StyleRegistry()
        r2 = r1.register(DefaultStyle())
        self.assertIsNot(r1, r2)
        self.assertEqual(r1.list_styles(), ())
        self.assertIn("default", r2.list_styles())

    def test_register_replaces_same_name(self):
        r = StyleRegistry().register(DefaultStyle()).register(DefaultStyle())
        self.assertEqual(r.list_styles().count("default"), 1)

    def test_get_registered(self):
        r = StyleRegistry().register(DefaultStyle())
        self.assertIsNotNone(r.get("default"))

    def test_get_missing(self):
        r = StyleRegistry()
        self.assertIsNone(r.get("nonexistent"))


class TestStyleRegistryActive(unittest.TestCase):
    def test_set_active(self):
        r = StyleRegistry().register(DefaultStyle()).set_active("default")
        self.assertIsNotNone(r.active)
        self.assertEqual(r.active.name, "default")

    def test_set_active_returns_new(self):
        r1 = StyleRegistry().register(DefaultStyle())
        r2 = r1.set_active("default")
        self.assertIsNot(r1, r2)
        self.assertIsNone(r1.active)

    def test_set_active_unknown_raises(self):
        r = StyleRegistry()
        with self.assertRaises(KeyError):
            r.set_active("nope")

    def test_active_none_when_unset(self):
        r = StyleRegistry().register(DefaultStyle())
        self.assertIsNone(r.active)
