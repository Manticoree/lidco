"""Tests for ChangelogGenerator, ChangeType, ChangeEntry."""
from __future__ import annotations

import unittest

from lidco.doc_intel.changelog_auto import ChangeEntry, ChangelogGenerator, ChangeType


class TestChangeTypeEnum(unittest.TestCase):
    def test_members(self):
        self.assertEqual(ChangeType.FEAT.value, "feat")
        self.assertEqual(ChangeType.FIX.value, "fix")
        self.assertEqual(ChangeType.BREAKING.value, "breaking")

    def test_is_str(self):
        self.assertIsInstance(ChangeType.FEAT, str)


class TestChangeEntryFrozen(unittest.TestCase):
    def test_creation(self):
        e = ChangeEntry(type=ChangeType.FEAT, description="add feature")
        self.assertEqual(e.type, ChangeType.FEAT)
        self.assertEqual(e.scope, "")
        self.assertEqual(e.pr_number, "")
        self.assertEqual(e.author, "")

    def test_frozen(self):
        e = ChangeEntry(type=ChangeType.FIX, description="d")
        with self.assertRaises(AttributeError):
            e.description = "other"  # type: ignore[misc]


class TestParseCommit(unittest.TestCase):
    def test_simple_feat(self):
        gen = ChangelogGenerator()
        entry = gen.parse_commit("feat: add login")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, ChangeType.FEAT)
        self.assertEqual(entry.description, "add login")

    def test_scoped(self):
        gen = ChangelogGenerator()
        entry = gen.parse_commit("fix(auth): handle expired tokens")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, ChangeType.FIX)
        self.assertEqual(entry.scope, "auth")
        self.assertEqual(entry.description, "handle expired tokens")

    def test_pr_number(self):
        gen = ChangelogGenerator()
        entry = gen.parse_commit("feat(ui): dark mode (#42)")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.pr_number, "42")

    def test_breaking_bang(self):
        gen = ChangelogGenerator()
        entry = gen.parse_commit("feat!: remove legacy API")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.type, ChangeType.BREAKING)

    def test_non_matching(self):
        gen = ChangelogGenerator()
        self.assertIsNone(gen.parse_commit("random commit message"))
        self.assertIsNone(gen.parse_commit("Update README"))

    def test_unknown_type(self):
        gen = ChangelogGenerator()
        self.assertIsNone(gen.parse_commit("xyz: something"))


class TestParseCommits(unittest.TestCase):
    def test_multiple(self):
        gen = ChangelogGenerator()
        msgs = [
            "feat: A",
            "garbage",
            "fix: B",
            "docs: C",
        ]
        entries = gen.parse_commits(msgs)
        self.assertEqual(len(entries), 3)
        types = [e.type for e in entries]
        self.assertIn(ChangeType.FEAT, types)
        self.assertIn(ChangeType.FIX, types)
        self.assertIn(ChangeType.DOCS, types)


class TestGenerate(unittest.TestCase):
    def test_keepachangelog_format(self):
        gen = ChangelogGenerator()
        entries = [
            ChangeEntry(type=ChangeType.FEAT, description="new feature"),
            ChangeEntry(type=ChangeType.FIX, description="bug fix", scope="core"),
        ]
        output = gen.generate(entries, version="1.0.0")
        self.assertIn("[1.0.0]", output)
        self.assertIn("### Added", output)
        self.assertIn("### Fixed", output)
        self.assertIn("new feature", output)
        self.assertIn("**core**: bug fix", output)

    def test_default_unreleased(self):
        gen = ChangelogGenerator()
        output = gen.generate([ChangeEntry(type=ChangeType.CHORE, description="cleanup")])
        self.assertIn("[Unreleased]", output)


class TestGroupByTypeAndSummary(unittest.TestCase):
    def test_group_by_type(self):
        gen = ChangelogGenerator()
        entries = [
            ChangeEntry(type=ChangeType.FEAT, description="A"),
            ChangeEntry(type=ChangeType.FEAT, description="B"),
            ChangeEntry(type=ChangeType.FIX, description="C"),
        ]
        grouped = gen.group_by_type(entries)
        self.assertEqual(len(grouped["feat"]), 2)
        self.assertEqual(len(grouped["fix"]), 1)

    def test_summary(self):
        gen = ChangelogGenerator()
        entries = [
            ChangeEntry(type=ChangeType.FEAT, description="A"),
            ChangeEntry(type=ChangeType.FIX, description="B"),
        ]
        s = gen.summary(entries)
        self.assertIn("1 feat", s)
        self.assertIn("1 fix", s)

    def test_summary_empty(self):
        gen = ChangelogGenerator()
        self.assertEqual(gen.summary([]), "No changes")


if __name__ == "__main__":
    unittest.main()
