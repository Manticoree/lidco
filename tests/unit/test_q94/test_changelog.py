"""Tests for T604 ChangelogGenerator."""
from unittest.mock import patch, MagicMock

import pytest

from lidco.git.changelog import (
    ChangelogGenerator,
    ChangelogRelease,
    ChangelogResult,
    ConventionalCommit,
    _parse_commit_block,
)


# Helper to call the private parser directly
def _parse(block: str):
    return _parse_commit_block(block)


SEP = chr(31)


# ---------------------------------------------------------------------------
# _parse_commit_block
# ---------------------------------------------------------------------------

class TestParseCommitBlock:
    def test_feat_commit(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01{SEP}feat: add new feature\n"
        commit = _parse(block)
        assert commit is not None
        assert commit.type == "feat"
        assert commit.description == "add new feature"
        assert commit.breaking is False

    def test_fix_commit_with_scope(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01{SEP}fix(auth): correct token expiry\n"
        commit = _parse(block)
        assert commit is not None
        assert commit.type == "fix"
        assert commit.scope == "auth"

    def test_breaking_change_exclamation(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01{SEP}feat!: remove old API\n"
        commit = _parse(block)
        assert commit is not None
        assert commit.breaking is True

    def test_breaking_change_footer(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01{SEP}feat: add thing\n\nBREAKING CHANGE: removes x\n"
        commit = _parse(block)
        assert commit is not None
        assert commit.breaking is True

    def test_non_conventional_returns_none(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01{SEP}just a regular commit message\n"
        commit = _parse(block)
        assert commit is None

    def test_empty_block_returns_none(self):
        assert _parse("") is None

    def test_malformed_block_returns_none(self):
        assert _parse("only_hash_no_fields") is None

    def test_date_truncated_to_10_chars(self):
        block = f"abc123{SEP}Alice{SEP}2026-01-01T12:34:56+00:00{SEP}feat: x\n"
        commit = _parse(block)
        assert commit is not None
        assert len(commit.date) == 10


# ---------------------------------------------------------------------------
# ChangelogRelease
# ---------------------------------------------------------------------------

class TestChangelogRelease:
    def test_is_empty_true(self):
        from lidco.git.changelog import ChangelogSection
        release = ChangelogRelease(
            version="v1.0.0",
            date="2026-01-01",
            sections=[ChangelogSection(title="Features")],
        )
        assert release.is_empty() is True

    def test_is_empty_false(self):
        from lidco.git.changelog import ChangelogSection
        section = ChangelogSection(title="Features")
        section.commits.append(ConventionalCommit(
            hash="abc", type="feat", scope="", description="add x",
            body="", breaking=False, date="2026-01-01", author="Alice", raw_message=""
        ))
        release = ChangelogRelease(version="v1.0.0", date="2026-01-01", sections=[section])
        assert release.is_empty() is False


# ---------------------------------------------------------------------------
# ChangelogResult.to_markdown
# ---------------------------------------------------------------------------

class TestToMarkdown:
    def _make_result(self) -> ChangelogResult:
        from lidco.git.changelog import ChangelogSection
        feat_section = ChangelogSection(title="Features")
        feat_section.commits.append(ConventionalCommit(
            hash="abc12345", type="feat", scope="auth", description="add login",
            body="", breaking=False, date="2026-01-01", author="Alice", raw_message=""
        ))
        fix_section = ChangelogSection(title="Bug Fixes")
        fix_section.commits.append(ConventionalCommit(
            hash="def67890", type="fix", scope="", description="fix crash",
            body="", breaking=False, date="2026-01-01", author="Bob", raw_message=""
        ))
        breaking_section = ChangelogSection(title="Breaking Changes")
        breaking_section.commits.append(ConventionalCommit(
            hash="bbb00000", type="feat", scope="", description="remove old API",
            body="", breaking=True, date="2026-01-01", author="Alice", raw_message=""
        ))
        release = ChangelogRelease(
            version="v2.0.0",
            date="2026-01-01",
            sections=[breaking_section, feat_section, fix_section],
        )
        return ChangelogResult(releases=[release], unrecognized_commits=[])

    def test_contains_version(self):
        md = self._make_result().to_markdown()
        assert "v2.0.0" in md

    def test_contains_section_headers(self):
        md = self._make_result().to_markdown()
        assert "### Features" in md
        assert "### Bug Fixes" in md

    def test_contains_commit_descriptions(self):
        md = self._make_result().to_markdown()
        assert "add login" in md
        assert "fix crash" in md

    def test_scope_bolded(self):
        md = self._make_result().to_markdown()
        assert "**auth**" in md

    def test_breaking_marker(self):
        md = self._make_result().to_markdown()
        assert "BREAKING" in md

    def test_empty_release_skipped(self):
        from lidco.git.changelog import ChangelogSection
        release = ChangelogRelease(
            version="v0.0.0", date="2026-01-01",
            sections=[ChangelogSection(title="Features")]
        )
        result = ChangelogResult(releases=[release], unrecognized_commits=[])
        md = result.to_markdown()
        assert "v0.0.0" not in md

    def test_hash_truncated_to_8(self):
        md = self._make_result().to_markdown()
        assert "abc12345" in md
        assert "abc12345678" not in md


# ---------------------------------------------------------------------------
# ChangelogGenerator
# ---------------------------------------------------------------------------

class TestChangelogGenerator:
    def _gen(self, **kwargs):
        return ChangelogGenerator(project_root="/fake", **kwargs)

    def test_generate_with_commits(self):
        sep = chr(31)
        log_sep = "---COMMIT---"
        block = f"abc12345678901234{sep}Alice{sep}2026-01-01{sep}feat: add thing\n{log_sep}"
        gen = self._gen()
        with patch("lidco.git.changelog._run_git", return_value=block):
            result = gen.generate()
        assert isinstance(result, ChangelogResult)

    def test_generate_empty_log(self):
        gen = self._gen()
        with patch("lidco.git.changelog._run_git", return_value=""):
            result = gen.generate()
        assert result.releases[0].is_empty()

    def test_unrecognized_commits_collected(self):
        sep = chr(31)
        log_sep = "---COMMIT---"
        block = f"abc123{sep}Alice{sep}2026-01-01{sep}just fixing stuff\n{log_sep}"
        gen = self._gen()
        with patch("lidco.git.changelog._run_git", return_value=block):
            result = gen.generate()
        assert len(result.unrecognized_commits) == 1

    def test_since_tag_passed_to_git(self):
        gen = self._gen(since_tag="v1.0.0")
        called_args = []
        def fake_git(args, cwd):
            called_args.extend(args)
            return ""
        with patch("lidco.git.changelog._run_git", side_effect=fake_git):
            gen.generate()
        assert any("v1.0.0" in a for a in called_args)

    def test_save_writes_file(self, tmp_path):
        gen = ChangelogGenerator(project_root=str(tmp_path), version="v1.0.0")
        from lidco.git.changelog import ChangelogSection, ChangelogRelease, ChangelogResult
        section = ChangelogSection(title="Features")
        section.commits.append(ConventionalCommit(
            hash="abc", type="feat", scope="", description="add x",
            body="", breaking=False, date="2026-01-01", author="Alice", raw_message=""
        ))
        result = ChangelogResult(
            releases=[ChangelogRelease(version="v1.0.0", date="2026-01-01", sections=[section])],
            unrecognized_commits=[],
        )
        path = gen.save(result)
        assert (tmp_path / "CHANGELOG.md").exists()

    def test_version_label_in_release(self):
        sep = chr(31)
        log_sep = "---COMMIT---"
        block = f"abc12345{sep}Alice{sep}2026-01-01{sep}feat: thing\n{log_sep}"
        gen = self._gen(version="v2.3.4")
        with patch("lidco.git.changelog._run_git", return_value=block):
            result = gen.generate()
        assert result.releases[0].version == "v2.3.4"

    def test_get_tags(self):
        gen = self._gen()
        with patch("lidco.git.changelog._run_git", return_value="v1.0.0\nv0.9.0\n"):
            tags = gen.get_tags()
        assert "v1.0.0" in tags
        assert "v0.9.0" in tags
