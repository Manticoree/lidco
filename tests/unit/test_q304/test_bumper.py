"""Tests for VersionBumper (Q304)."""

import pytest

from lidco.release.bumper import VersionBumper


class TestVersionBumperCurrent:
    def _make(self):
        return VersionBumper()

    def test_parse_basic(self):
        assert self._make().current("1.2.3") == (1, 2, 3)

    def test_parse_with_v_prefix(self):
        assert self._make().current("v1.0.0") == (1, 0, 0)

    def test_parse_zero(self):
        assert self._make().current("0.0.0") == (0, 0, 0)

    def test_parse_large_numbers(self):
        assert self._make().current("100.200.300") == (100, 200, 300)

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            self._make().current("not-a-version")

    def test_parse_incomplete_raises(self):
        with pytest.raises(ValueError):
            self._make().current("1.2")

    def test_parse_trailing_spaces(self):
        assert self._make().current("  2.3.4  ") == (2, 3, 4)

    def test_parse_negative_raises(self):
        with pytest.raises(ValueError):
            self._make().current("-1.0.0")


class TestVersionBumperBump:
    def _make(self):
        return VersionBumper()

    def test_bump_major(self):
        assert self._make().bump_major("1.2.3") == "2.0.0"

    def test_bump_major_resets_minor_patch(self):
        assert self._make().bump_major("0.9.8") == "1.0.0"

    def test_bump_minor(self):
        assert self._make().bump_minor("1.2.3") == "1.3.0"

    def test_bump_minor_resets_patch(self):
        assert self._make().bump_minor("2.5.9") == "2.6.0"

    def test_bump_patch(self):
        assert self._make().bump_patch("1.2.3") == "1.2.4"

    def test_bump_patch_from_zero(self):
        assert self._make().bump_patch("0.0.0") == "0.0.1"

    def test_bump_major_from_v_prefix(self):
        assert self._make().bump_major("v3.2.1") == "4.0.0"

    def test_bump_invalid_raises(self):
        with pytest.raises(ValueError):
            self._make().bump_patch("bad")


class TestVersionBumperDetect:
    def _make(self):
        return VersionBumper()

    def test_detect_major_from_breaking(self):
        commits = ["BREAKING CHANGE: removed old API"]
        assert self._make().detect_bump_type(commits) == "major"

    def test_detect_major_from_bang(self):
        commits = ["feat!: new interface"]
        assert self._make().detect_bump_type(commits) == "major"

    def test_detect_minor_from_feat(self):
        commits = ["feat: add new feature", "fix: typo"]
        assert self._make().detect_bump_type(commits) == "minor"

    def test_detect_patch_from_fixes(self):
        commits = ["fix: correct typo", "chore: update deps"]
        assert self._make().detect_bump_type(commits) == "patch"

    def test_detect_patch_empty(self):
        assert self._make().detect_bump_type([]) == "patch"

    def test_from_commits_major(self):
        commits = ["BREAKING CHANGE: drop v1 API"]
        assert self._make().from_commits(commits, "1.0.0") == "2.0.0"

    def test_from_commits_minor(self):
        commits = ["feat: new widget"]
        assert self._make().from_commits(commits, "1.0.0") == "1.1.0"

    def test_from_commits_patch(self):
        commits = ["fix: null pointer"]
        assert self._make().from_commits(commits, "1.0.0") == "1.0.1"
