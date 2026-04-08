"""Tests for CommandDedupValidator (Q340 Task 1)."""
from __future__ import annotations

import unittest


class TestFindDuplicatesNone(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_dedup import CommandDedupValidator
        self.v = CommandDedupValidator()

    def test_no_commands_returns_empty(self):
        result = self.v.find_duplicates([])
        self.assertEqual(result, [])

    def test_all_unique_returns_empty(self):
        commands = [
            {"name": "foo", "description": "Foo", "line": 10},
            {"name": "bar", "description": "Bar", "line": 20},
        ]
        result = self.v.find_duplicates(commands)
        self.assertEqual(result, [])


class TestFindDuplicatesWithDupes(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_dedup import CommandDedupValidator
        self.v = CommandDedupValidator()
        self.commands = [
            {"name": "foo", "description": "First", "line": 10},
            {"name": "bar", "description": "Bar", "line": 20},
            {"name": "foo", "description": "Second", "line": 30},
        ]

    def test_finds_duplicate_name(self):
        result = self.v.find_duplicates(self.commands)
        names = [d["name"] for d in result]
        self.assertIn("foo", names)

    def test_winner_is_last_line(self):
        result = self.v.find_duplicates(self.commands)
        dup = next(d for d in result if d["name"] == "foo")
        self.assertEqual(dup["winner"], 30)

    def test_registrations_contains_all_lines(self):
        result = self.v.find_duplicates(self.commands)
        dup = next(d for d in result if d["name"] == "foo")
        self.assertIn(10, dup["registrations"])
        self.assertIn(30, dup["registrations"])

    def test_no_false_positives(self):
        result = self.v.find_duplicates(self.commands)
        names = [d["name"] for d in result]
        self.assertNotIn("bar", names)


class TestAnalyzeShadows(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_dedup import CommandDedupValidator
        self.v = CommandDedupValidator()

    def test_no_shadows_when_unique(self):
        commands = [
            {"name": "a", "description": "A", "line": 1},
            {"name": "b", "description": "B", "line": 2},
        ]
        self.assertEqual(self.v.analyze_shadows(commands), [])

    def test_detects_shadow(self):
        commands = [
            {"name": "cmd", "description": "First", "line": 5},
            {"name": "cmd", "description": "Second", "line": 15},
        ]
        result = self.v.analyze_shadows(commands)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shadowed_name"], "cmd")
        self.assertEqual(result[0]["original_line"], 5)
        self.assertEqual(result[0]["shadow_line"], 15)

    def test_shadow_description_is_from_shadowing_registration(self):
        commands = [
            {"name": "cmd", "description": "Old", "line": 5},
            {"name": "cmd", "description": "New", "line": 15},
        ]
        result = self.v.analyze_shadows(commands)
        self.assertEqual(result[0]["description"], "New")


class TestTrackOverrideChain(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_dedup import CommandDedupValidator
        self.v = CommandDedupValidator()

    def test_single_registration(self):
        cmds = [{"name": "x", "description": "", "line": 1}]
        chain = self.v.track_override_chain(cmds)
        self.assertIn("x", chain)
        self.assertEqual(len(chain["x"]), 1)

    def test_multiple_registrations_ordered(self):
        cmds = [
            {"name": "x", "description": "a", "line": 1},
            {"name": "x", "description": "b", "line": 2},
            {"name": "x", "description": "c", "line": 3},
        ]
        chain = self.v.track_override_chain(cmds)
        self.assertEqual(len(chain["x"]), 3)
        self.assertEqual(chain["x"][0]["line"], 1)
        self.assertEqual(chain["x"][-1]["line"], 3)


class TestSuggestFixes(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_dedup import CommandDedupValidator
        self.v = CommandDedupValidator()

    def test_no_suggestions_when_no_duplicates(self):
        self.assertEqual(self.v.suggest_fixes([]), [])

    def test_suggestion_mentions_command_name(self):
        duplicates = [{"name": "foo", "registrations": [10, 30], "winner": 30}]
        fixes = self.v.suggest_fixes(duplicates)
        self.assertEqual(len(fixes), 1)
        self.assertIn("foo", fixes[0])

    def test_suggestion_mentions_winner_line(self):
        duplicates = [{"name": "bar", "registrations": [5, 20], "winner": 20}]
        fixes = self.v.suggest_fixes(duplicates)
        self.assertIn("20", fixes[0])

    def test_suggestion_mentions_loser_line(self):
        duplicates = [{"name": "baz", "registrations": [5, 20], "winner": 20}]
        fixes = self.v.suggest_fixes(duplicates)
        self.assertIn("5", fixes[0])


if __name__ == "__main__":
    unittest.main()
