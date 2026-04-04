"""Tests for ReleaseNotesGenerator (Q304)."""

import pytest

from lidco.release.notes import ReleaseEntry, ReleaseNotesGenerator


class TestReleaseNotesHighlights:
    def _make(self):
        return ReleaseNotesGenerator()

    def test_highlights_added(self):
        entries = [ReleaseEntry(type="added", message="new widget")]
        assert self._make().highlights(entries) == ["new widget"]

    def test_highlights_changed(self):
        entries = [ReleaseEntry(type="changed", message="updated API")]
        assert self._make().highlights(entries) == ["updated API"]

    def test_highlights_excludes_fixed(self):
        entries = [ReleaseEntry(type="fixed", message="bug")]
        assert self._make().highlights(entries) == []

    def test_highlights_multiple(self):
        entries = [
            ReleaseEntry(type="added", message="A"),
            ReleaseEntry(type="changed", message="B"),
            ReleaseEntry(type="fixed", message="C"),
        ]
        assert self._make().highlights(entries) == ["A", "B"]

    def test_highlights_empty(self):
        assert self._make().highlights([]) == []

    def test_highlights_preserves_order(self):
        entries = [
            ReleaseEntry(type="added", message="first"),
            ReleaseEntry(type="added", message="second"),
        ]
        assert self._make().highlights(entries) == ["first", "second"]

    def test_highlights_ignores_removed(self):
        entries = [ReleaseEntry(type="removed", message="old code")]
        assert self._make().highlights(entries) == []

    def test_highlights_mixed(self):
        entries = [
            ReleaseEntry(type="added", message="X"),
            ReleaseEntry(type="deprecated", message="Y"),
            ReleaseEntry(type="changed", message="Z"),
        ]
        assert self._make().highlights(entries) == ["X", "Z"]


class TestReleaseNotesBreaking:
    def _make(self):
        return ReleaseNotesGenerator()

    def test_breaking_changes(self):
        entries = [ReleaseEntry(type="changed", message="drop v1", breaking=True)]
        assert self._make().breaking_changes(entries) == ["drop v1"]

    def test_no_breaking(self):
        entries = [ReleaseEntry(type="added", message="x")]
        assert self._make().breaking_changes(entries) == []

    def test_breaking_multiple(self):
        entries = [
            ReleaseEntry(type="removed", message="A", breaking=True),
            ReleaseEntry(type="changed", message="B", breaking=True),
        ]
        assert len(self._make().breaking_changes(entries)) == 2

    def test_breaking_empty(self):
        assert self._make().breaking_changes([]) == []


class TestReleaseNotesContributors:
    def _make(self):
        return ReleaseNotesGenerator()

    def test_contributors_sorted(self):
        entries = [
            ReleaseEntry(type="added", message="x", author="Zara"),
            ReleaseEntry(type="fixed", message="y", author="Alice"),
        ]
        assert self._make().contributors(entries) == ["Alice", "Zara"]

    def test_contributors_dedup(self):
        entries = [
            ReleaseEntry(type="added", message="x", author="Bob"),
            ReleaseEntry(type="fixed", message="y", author="Bob"),
        ]
        assert self._make().contributors(entries) == ["Bob"]

    def test_contributors_empty_author(self):
        entries = [ReleaseEntry(type="added", message="x")]
        assert self._make().contributors(entries) == []

    def test_contributors_empty(self):
        assert self._make().contributors([]) == []


class TestReleaseNotesMigrationGuide:
    def _make(self):
        return ReleaseNotesGenerator()

    def test_migration_guide(self):
        changes = ["API v1 removed", "Config format changed"]
        result = self._make().migration_guide(changes)
        assert "Migration Guide" in result
        assert "1. API v1 removed" in result
        assert "2. Config format changed" in result

    def test_migration_guide_empty(self):
        assert self._make().migration_guide([]) == ""

    def test_migration_guide_single(self):
        result = self._make().migration_guide(["drop old API"])
        assert "1. drop old API" in result


class TestReleaseNotesGenerate:
    def _make(self):
        return ReleaseNotesGenerator()

    def test_generate_full(self):
        entries = [
            ReleaseEntry(type="added", message="new feature", author="Alice"),
            ReleaseEntry(type="fixed", message="crash fix", author="Bob"),
            ReleaseEntry(type="changed", message="drop v1", breaking=True, author="Alice"),
        ]
        result = self._make().generate("2.0.0", entries)
        assert "# Release 2.0.0" in result
        assert "Highlights" in result
        assert "Breaking Changes" in result
        assert "Bug Fixes" in result
        assert "Contributors" in result

    def test_generate_empty(self):
        result = self._make().generate("1.0.0", [])
        assert "# Release 1.0.0" in result

    def test_generate_no_breaking(self):
        entries = [ReleaseEntry(type="added", message="feature")]
        result = self._make().generate("1.1.0", entries)
        assert "Breaking" not in result

    def test_generate_no_highlights(self):
        entries = [ReleaseEntry(type="fixed", message="typo")]
        result = self._make().generate("1.0.1", entries)
        assert "Highlights" not in result
        assert "Bug Fixes" in result
