"""Tests for T600 PRDescriptionGenerator."""
from unittest.mock import MagicMock, patch

import pytest

from lidco.git.pr_description import (
    DiffStats,
    PRDescription,
    PRDescriptionGenerator,
    _parse_log,
    _parse_numstat,
    _run_git,
)


# ---------------------------------------------------------------------------
# _parse_log
# ---------------------------------------------------------------------------

class TestParseLog:
    def test_single_commit(self):
        raw = "abc\x1fAlice\x1f2026-01-01\x1fFix thing\x1e"
        commits = _parse_log(raw)
        assert len(commits) == 1
        assert commits[0]["message"] == "Fix thing"

    def test_empty_returns_empty(self):
        assert _parse_log("") == []

    def test_multiple_commits(self):
        raw = "a\x1fA\x1f2026-01-01\x1fFirst\x1eb\x1fB\x1f2026-01-02\x1fSecond\x1e"
        assert len(_parse_log(raw)) == 2


# ---------------------------------------------------------------------------
# _parse_numstat
# ---------------------------------------------------------------------------

class TestParseNumstat:
    def test_basic(self):
        raw = "10\t5\tsrc/foo.py\n2\t0\ttests/test_foo.py\n"
        ins, dels, files = _parse_numstat(raw)
        assert ins == 12
        assert dels == 5
        assert "src/foo.py" in files

    def test_empty(self):
        ins, dels, files = _parse_numstat("")
        assert ins == 0
        assert dels == 0
        assert files == []

    def test_binary_lines_skipped(self):
        raw = "-\t-\timage.png\n5\t2\tfoo.py\n"
        ins, dels, files = _parse_numstat(raw)
        assert ins == 5
        assert dels == 2


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------

class TestRunGit:
    def test_returns_stdout(self, tmp_path):
        fake = MagicMock()
        fake.stdout = "result\n"
        with patch("lidco.git.pr_description.subprocess.run", return_value=fake):
            assert _run_git(["log"], str(tmp_path)) == "result\n"

    def test_exception_returns_empty(self, tmp_path):
        with patch("lidco.git.pr_description.subprocess.run", side_effect=Exception):
            assert _run_git(["log"], str(tmp_path)) == ""


# ---------------------------------------------------------------------------
# PRDescription dataclass
# ---------------------------------------------------------------------------

class TestPRDescription:
    def test_has_breaking_changes_true(self):
        desc = PRDescription(
            title="X", summary=[], changes=[], test_plan=[],
            breaking_changes=["Removed old API"]
        )
        assert desc.has_breaking_changes is True

    def test_has_breaking_changes_false(self):
        desc = PRDescription(
            title="X", summary=[], changes=[], test_plan=[], breaking_changes=[]
        )
        assert desc.has_breaking_changes is False


# ---------------------------------------------------------------------------
# PRDescriptionGenerator
# ---------------------------------------------------------------------------

class TestPRDescriptionGenerator:
    def _make_gen(self, llm=None):
        return PRDescriptionGenerator(project_root="/fake", llm_callback=llm)

    def _fake_stats(self, commits=None, files=None):
        default_commits = [{"hash": "abc", "author": "Alice", "date": "2026-01-01", "message": "Add feature"}]
        actual_commits = commits if commits is not None else default_commits
        return DiffStats(
            base_branch="main",
            head_branch="feature",
            commit_count=len(actual_commits),
            files_changed=files if files is not None else ["src/foo.py"],
            insertions=10,
            deletions=3,
            commits=actual_commits,
            diff_summary="1 file changed",
        )

    # --- rule-based ---

    def test_rule_based_title_from_commit(self):
        gen = self._make_gen()
        stats = self._fake_stats()
        desc = gen._rule_based_generate(stats)
        assert desc.title == "Add feature"

    def test_rule_based_fallback_title(self):
        gen = self._make_gen()
        stats = self._fake_stats(commits=[])
        stats.head_branch = "my-branch"
        desc = gen._rule_based_generate(stats)
        assert "my-branch" in desc.title

    def test_rule_based_summary_has_commit_count(self):
        gen = self._make_gen()
        stats = self._fake_stats()
        desc = gen._rule_based_generate(stats)
        assert any("1" in s for s in desc.summary)

    def test_rule_based_test_plan_present(self):
        gen = self._make_gen()
        stats = self._fake_stats()
        desc = gen._rule_based_generate(stats)
        assert len(desc.test_plan) >= 1

    def test_rule_based_breaking_change_detection(self):
        gen = self._make_gen()
        stats = self._fake_stats(commits=[
            {"hash": "aaa", "author": "Alice", "date": "2026-01-01", "message": "BREAKING: remove old endpoint"}
        ])
        desc = gen._rule_based_generate(stats)
        assert desc.has_breaking_changes

    def test_rule_based_no_breaking_changes(self):
        gen = self._make_gen()
        stats = self._fake_stats()
        desc = gen._rule_based_generate(stats)
        assert not desc.has_breaking_changes

    # --- LLM-based ---

    LLM_RESPONSE = """\
TITLE: Add awesome feature
SUMMARY:
- Implements the new feature
- Updates tests
CHANGES:
- Modified src/foo.py to add logic
BREAKING CHANGES:
- none
TEST PLAN:
- [ ] Run full test suite
- [ ] Manual smoke test
"""

    def test_llm_generate_parses_title(self):
        gen = self._make_gen(llm=lambda _: self.LLM_RESPONSE)
        stats = self._fake_stats()
        desc = gen._llm_generate(stats)
        assert desc.title == "Add awesome feature"

    def test_llm_generate_parses_summary(self):
        gen = self._make_gen(llm=lambda _: self.LLM_RESPONSE)
        stats = self._fake_stats()
        desc = gen._llm_generate(stats)
        assert len(desc.summary) >= 1

    def test_llm_generate_parses_test_plan(self):
        gen = self._make_gen(llm=lambda _: self.LLM_RESPONSE)
        stats = self._fake_stats()
        desc = gen._llm_generate(stats)
        assert len(desc.test_plan) >= 1

    def test_llm_generate_no_breaking_changes(self):
        gen = self._make_gen(llm=lambda _: self.LLM_RESPONSE)
        stats = self._fake_stats()
        desc = gen._llm_generate(stats)
        assert not desc.has_breaking_changes

    def test_llm_fallback_title_from_commits(self):
        # LLM response without TITLE: line → fallback to first commit message
        gen = self._make_gen(llm=lambda _: "SUMMARY:\n- something\nTEST PLAN:\n- test it\n")
        stats = self._fake_stats()
        desc = gen._llm_generate(stats)
        assert desc.title == "Add feature"  # from first commit

    # --- format_markdown ---

    def test_format_markdown_contains_title(self):
        gen = self._make_gen()
        desc = PRDescription(
            title="My PR",
            summary=["Does X"],
            changes=["Modified foo.py"],
            test_plan=["Run tests"],
            breaking_changes=[],
        )
        md = gen.format_markdown(desc)
        assert "## My PR" in md
        assert "- Does X" in md
        assert "- [ ] Run tests" in md

    def test_format_markdown_breaking_changes(self):
        gen = self._make_gen()
        desc = PRDescription(
            title="X", summary=[], changes=[],
            test_plan=[], breaking_changes=["Old API removed"]
        )
        md = gen.format_markdown(desc)
        assert "Breaking Changes" in md
        assert "Old API removed" in md

    # --- format_github ---

    def test_format_github_contains_summary_header(self):
        gen = self._make_gen()
        desc = PRDescription(
            title="X", summary=["Thing 1"], changes=[],
            test_plan=["Test it"], breaking_changes=[]
        )
        body = gen.format_github(desc)
        assert "## Summary" in body
        assert "LIDCO" in body

    def test_format_github_breaking_changes(self):
        gen = self._make_gen()
        desc = PRDescription(
            title="X", summary=[], changes=[],
            test_plan=[], breaking_changes=["Removed endpoint"]
        )
        body = gen.format_github(desc)
        assert "Breaking Changes" in body

    # --- generate (integration) ---

    def test_generate_calls_rule_based_without_llm(self):
        gen = self._make_gen()
        fake_log = "abc\x1fAlice\x1f2026-01-01\x1fFix thing\x1e"
        fake_stat = "5\t2\tsrc/foo.py\n"
        fake_diff = "1 file changed"

        with patch("lidco.git.pr_description._run_git") as mock_git:
            mock_git.side_effect = [fake_log, fake_stat, fake_diff, "feature"]
            desc = gen.generate(base_branch="main")

        assert isinstance(desc, PRDescription)
        assert desc.title  # not empty

    def test_generate_calls_llm_when_provided(self):
        llm = MagicMock(return_value=self.LLM_RESPONSE)
        gen = self._make_gen(llm=llm)
        fake_log = "abc\x1fAlice\x1f2026-01-01\x1fFix thing\x1e"
        fake_stat = "5\t2\tsrc/foo.py\n"
        fake_diff = "1 file changed"

        with patch("lidco.git.pr_description._run_git") as mock_git:
            mock_git.side_effect = [fake_log, fake_stat, fake_diff, "feature"]
            desc = gen.generate(base_branch="main")

        llm.assert_called_once()
        assert desc.title == "Add awesome feature"

    def test_build_prompt_contains_branch_info(self):
        gen = self._make_gen()
        stats = self._fake_stats()
        prompt = gen._build_prompt(stats)
        assert "feature" in prompt
        assert "main" in prompt
        assert "Add feature" in prompt
