"""Tests for CommandAlias (Q145 Task 858)."""
from __future__ import annotations

import unittest

from lidco.ux.command_alias import CommandAlias, Alias


class TestAlias(unittest.TestCase):
    def test_dataclass_fields(self):
        a = Alias(name="b", expansion="/build", description="build shortcut")
        self.assertEqual(a.name, "b")
        self.assertEqual(a.expansion, "/build")
        self.assertEqual(a.description, "build shortcut")
        self.assertEqual(a.usage_count, 0)

    def test_default_usage_count(self):
        a = Alias(name="x", expansion="/exit")
        self.assertEqual(a.usage_count, 0)


class TestCommandAlias(unittest.TestCase):
    def setUp(self):
        self.ca = CommandAlias()

    def test_add_and_is_alias(self):
        self.ca.add("b", "/build")
        self.assertTrue(self.ca.is_alias("b"))

    def test_is_alias_false(self):
        self.assertFalse(self.ca.is_alias("nope"))

    def test_resolve_known_alias(self):
        self.ca.add("b", "/build")
        self.assertEqual(self.ca.resolve("b"), "/build")

    def test_resolve_alias_with_args(self):
        self.ca.add("b", "/build")
        self.assertEqual(self.ca.resolve("b --fast"), "/build --fast")

    def test_resolve_unknown_returns_input(self):
        result = self.ca.resolve("unknown stuff")
        self.assertEqual(result, "unknown stuff")

    def test_resolve_empty_returns_empty(self):
        self.assertEqual(self.ca.resolve(""), "")

    def test_resolve_increments_usage(self):
        self.ca.add("b", "/build")
        self.ca.resolve("b")
        self.ca.resolve("b")
        aliases = self.ca.list_aliases()
        self.assertEqual(aliases[0].usage_count, 2)

    def test_remove_existing(self):
        self.ca.add("b", "/build")
        self.assertTrue(self.ca.remove("b"))
        self.assertFalse(self.ca.is_alias("b"))

    def test_remove_nonexistent(self):
        self.assertFalse(self.ca.remove("nope"))

    def test_list_aliases_sorted(self):
        self.ca.add("z", "/zzz")
        self.ca.add("a", "/aaa")
        self.ca.add("m", "/mmm")
        aliases = self.ca.list_aliases()
        names = [a.name for a in aliases]
        self.assertEqual(names, ["a", "m", "z"])

    def test_list_aliases_empty(self):
        self.assertEqual(self.ca.list_aliases(), [])

    def test_most_used(self):
        self.ca.add("a", "/aaa")
        self.ca.add("b", "/bbb")
        self.ca.resolve("a")
        self.ca.resolve("a")
        self.ca.resolve("b")
        top = self.ca.most_used(1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].name, "a")

    def test_most_used_empty(self):
        self.assertEqual(self.ca.most_used(), [])

    def test_add_overwrites_existing(self):
        self.ca.add("b", "/build")
        self.ca.add("b", "/build-all")
        self.assertEqual(self.ca.resolve("b"), "/build-all")

    def test_add_with_description(self):
        self.ca.add("b", "/build", "Run build")
        aliases = self.ca.list_aliases()
        self.assertEqual(aliases[0].description, "Run build")

    def test_most_used_respects_n(self):
        for i in range(10):
            self.ca.add(f"a{i}", f"/cmd{i}")
            for _ in range(i):
                self.ca.resolve(f"a{i}")
        result = self.ca.most_used(3)
        self.assertEqual(len(result), 3)

    def test_resolve_only_first_word(self):
        self.ca.add("b", "/build")
        # "bb" should not match "b"
        self.assertEqual(self.ca.resolve("bb"), "bb")

    def test_usage_count_survives_list(self):
        self.ca.add("b", "/build")
        self.ca.resolve("b")
        self.ca.resolve("b")
        self.ca.resolve("b")
        self.assertEqual(self.ca.list_aliases()[0].usage_count, 3)


if __name__ == "__main__":
    unittest.main()
