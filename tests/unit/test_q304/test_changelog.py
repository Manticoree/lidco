"""Tests for ChangelogGenerator2 (Q304)."""

import pytest

from lidco.release.changelog import ChangelogGenerator2


class TestChangelogGenerator2AddEntry:
    def _make(self):
        return ChangelogGenerator2()

    def test_add_entry(self):
        gen = self._make()
        gen.add_entry("added", "new feature")
        assert len(gen.entries) == 1

    def test_add_multiple_entries(self):
        gen = self._make()
        gen.add_entry("added", "feature A")
        gen.add_entry("fixed", "bug B")
        assert len(gen.entries) == 2

    def test_entry_type_lowercased(self):
        gen = self._make()
        gen.add_entry("ADDED", "something")
        assert gen.entries[0].type == "added"

    def test_entry_with_pr_url(self):
        gen = self._make()
        gen.add_entry("fixed", "bug", pr_url="https://github.com/pr/1")
        assert gen.entries[0].pr_url == "https://github.com/pr/1"

    def test_entries_immutable_copy(self):
        gen = self._make()
        gen.add_entry("added", "x")
        entries = gen.entries
        entries.clear()
        assert len(gen.entries) == 1

    def test_entry_no_pr_url_default(self):
        gen = self._make()
        gen.add_entry("changed", "updated API")
        assert gen.entries[0].pr_url == ""

    def test_add_preserves_order(self):
        gen = self._make()
        gen.add_entry("added", "first")
        gen.add_entry("fixed", "second")
        gen.add_entry("removed", "third")
        messages = [e.message for e in gen.entries]
        assert messages == ["first", "second", "third"]

    def test_empty_entries(self):
        gen = self._make()
        assert gen.entries == []


class TestChangelogGenerator2GroupByType:
    def _make(self):
        return ChangelogGenerator2()

    def test_group_single_type(self):
        gen = self._make()
        gen.add_entry("added", "A")
        gen.add_entry("added", "B")
        groups = gen.group_by_type()
        assert len(groups["added"]) == 2

    def test_group_multiple_types(self):
        gen = self._make()
        gen.add_entry("added", "A")
        gen.add_entry("fixed", "B")
        groups = gen.group_by_type()
        assert "added" in groups
        assert "fixed" in groups

    def test_group_empty(self):
        gen = self._make()
        assert gen.group_by_type() == {}


class TestChangelogGenerator2Generate:
    def _make(self):
        return ChangelogGenerator2()

    def test_generate_empty(self):
        gen = self._make()
        result = gen.generate("1.0.0")
        assert "No changes" in result

    def test_generate_with_entries(self):
        gen = self._make()
        gen.add_entry("added", "new feature")
        result = gen.generate("2.0.0")
        assert "# 2.0.0" in result
        assert "new feature" in result

    def test_generate_includes_pr_url(self):
        gen = self._make()
        gen.add_entry("fixed", "bug", pr_url="https://example.com/pr/1")
        result = gen.generate("1.1.0")
        assert "https://example.com/pr/1" in result

    def test_keep_a_changelog_format(self):
        gen = self._make()
        gen.add_entry("added", "feature X")
        gen.add_entry("fixed", "bug Y")
        result = gen.keep_a_changelog_format("3.0.0", "2026-04-04")
        assert "## [3.0.0] - 2026-04-04" in result
        assert "### Added" in result
        assert "### Fixed" in result

    def test_keep_a_changelog_canonical_order(self):
        gen = self._make()
        gen.add_entry("fixed", "F")
        gen.add_entry("added", "A")
        result = gen.keep_a_changelog_format("1.0.0", "2026-01-01")
        added_pos = result.index("### Added")
        fixed_pos = result.index("### Fixed")
        assert added_pos < fixed_pos

    def test_keep_a_changelog_defaults_date(self):
        gen = self._make()
        gen.add_entry("added", "item")
        result = gen.keep_a_changelog_format("1.0.0")
        assert "## [1.0.0]" in result
