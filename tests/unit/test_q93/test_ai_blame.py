"""Tests for T599 AIBlameAnalyzer."""
from unittest.mock import patch, MagicMock

import pytest

from lidco.git.ai_blame import (
    AIBlameAnalyzer,
    BlameEntry,
    FileHistory,
    _parse_blame,
    _parse_log,
    _run_git,
)


# ---------------------------------------------------------------------------
# _parse_log
# ---------------------------------------------------------------------------

class TestParseLog:
    def test_single_commit(self):
        raw = "abc123\x1fAlice\x1f2026-01-01\x1fFix bug\x1e"
        commits = _parse_log(raw)
        assert len(commits) == 1
        assert commits[0]["hash"] == "abc123"
        assert commits[0]["author"] == "Alice"
        assert commits[0]["message"] == "Fix bug"

    def test_multiple_commits(self):
        raw = "aaa\x1fA\x1f2026-01-01\x1fFirst\x1ebbb\x1fB\x1f2026-01-02\x1fSecond\x1e"
        commits = _parse_log(raw)
        assert len(commits) == 2

    def test_empty_returns_empty(self):
        assert _parse_log("") == []

    def test_malformed_block_skipped(self):
        raw = "only_one_field\x1e"
        commits = _parse_log(raw)
        assert commits == []


# ---------------------------------------------------------------------------
# _parse_blame
# ---------------------------------------------------------------------------

SAMPLE_BLAME = """\
a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2 1 1 2
author Alice
author-time 1700000000
summary Add initial implementation
\tdef foo():
\t    pass
a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2 2 2
author Alice
author-time 1700000000
summary Add initial implementation
\t    return 42
d1e2f3a4b5c6d1e2f3a4b5c6d1e2f3a4b5c6d1e2 3 3 1
author Bob
author-time 1700000001
summary Fix return value
\t    return 43
"""


class TestParseBlame:
    def test_parses_entries(self):
        entries = _parse_blame(SAMPLE_BLAME, "foo.py")
        assert len(entries) >= 1

    def test_entry_has_author(self):
        entries = _parse_blame(SAMPLE_BLAME, "foo.py")
        authors = {e.author for e in entries}
        assert "Alice" in authors or "Bob" in authors

    def test_empty_blame_returns_empty(self):
        entries = _parse_blame("", "foo.py")
        assert entries == []

    def test_entry_file_set(self):
        entries = _parse_blame(SAMPLE_BLAME, "myfile.py")
        for e in entries:
            assert e.file == "myfile.py"


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------

class TestRunGit:
    def test_returns_stdout(self, tmp_path):
        fake_proc = MagicMock()
        fake_proc.stdout = "output\n"
        with patch("lidco.git.ai_blame.subprocess.run", return_value=fake_proc):
            result = _run_git(["log"], str(tmp_path))
        assert result == "output\n"

    def test_exception_returns_empty(self, tmp_path):
        with patch("lidco.git.ai_blame.subprocess.run", side_effect=Exception("no git")):
            result = _run_git(["log"], str(tmp_path))
        assert result == ""


# ---------------------------------------------------------------------------
# AIBlameAnalyzer
# ---------------------------------------------------------------------------

class TestAIBlameAnalyzer:
    def _make_analyzer(self, llm=None):
        return AIBlameAnalyzer(project_root="/fake", llm_callback=llm)

    def test_analyze_file_no_llm(self):
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=SAMPLE_BLAME):
            entries = analyzer.analyze_file("foo.py")
        assert isinstance(entries, list)
        # Each entry is a BlameEntry
        for e in entries:
            assert isinstance(e, BlameEntry)

    def test_analyze_file_with_llm(self):
        llm = MagicMock(return_value="This code initialises the foo function.")
        analyzer = self._make_analyzer(llm=llm)
        with patch("lidco.git.ai_blame._run_git", return_value=SAMPLE_BLAME):
            entries = analyzer.analyze_file("foo.py")
        # LLM should have been called for entries
        if entries:
            assert any(e.ai_explanation for e in entries)

    def test_analyze_file_with_line_range(self):
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=SAMPLE_BLAME) as mock_git:
            analyzer.analyze_file("foo.py", line_range=(1, 5))
        # Verify -L flag was passed
        called_args = mock_git.call_args[0][0]
        assert any("-L" in a for a in called_args)

    def test_explain_history_no_llm(self):
        log_raw = "abc\x1fAlice\x1f2026-01-01\x1fFix bug\x1e"
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            result = analyzer.explain_history("foo.py")
        assert "Alice" in result or "Fix bug" in result

    def test_explain_history_with_llm(self):
        log_raw = "abc\x1fAlice\x1f2026-01-01\x1fFix bug\x1e"
        llm = MagicMock(return_value="The file evolved significantly over time.")
        analyzer = self._make_analyzer(llm=llm)
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            result = analyzer.explain_history("foo.py")
        assert "evolved" in result

    def test_explain_history_empty_returns_placeholder(self):
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=""):
            result = analyzer.explain_history("foo.py")
        assert result == "(no history)"

    def test_find_introduction_found(self):
        log_raw = "abc123\x1fAlice\x1f2026-01-01\x1fAdd my_func\x1e"
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            entry = analyzer.find_introduction("my_func")
        assert entry is not None
        assert entry.author == "Alice"
        assert entry.message == "Add my_func"

    def test_find_introduction_not_found(self):
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=""):
            entry = analyzer.find_introduction("nonexistent_symbol")
        assert entry is None

    def test_find_introduction_with_llm(self):
        log_raw = "abc123\x1fAlice\x1f2026-01-01\x1fAdd my_func\x1e"
        llm = MagicMock(return_value="my_func was added to handle edge cases.")
        analyzer = self._make_analyzer(llm=llm)
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            entry = analyzer.find_introduction("my_func")
        assert entry is not None
        assert entry.ai_explanation != ""

    def test_get_file_history_no_llm(self):
        log_raw = "abc\x1fAlice\x1f2026-01-01\x1fFix bug\x1e"
        analyzer = self._make_analyzer()
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            history = analyzer.get_file_history("foo.py")
        assert isinstance(history, FileHistory)
        assert len(history.commits) == 1
        assert history.ai_summary == ""

    def test_get_file_history_with_llm(self):
        log_raw = "abc\x1fAlice\x1f2026-01-01\x1fFix bug\x1e"
        llm = MagicMock(return_value="Short summary.")
        analyzer = self._make_analyzer(llm=llm)
        with patch("lidco.git.ai_blame._run_git", return_value=log_raw):
            history = analyzer.get_file_history("foo.py")
        assert history.ai_summary == "Short summary."

    def test_max_entries_limits_llm_calls(self):
        # Generate many blame blocks
        hash1 = "a" * 40
        blame_lines = []
        for i in range(1, 30):
            blame_lines.append(f"{hash1} {i} {i} 1")
            blame_lines.append("author Alice")
            blame_lines.append("author-time 1700000000")
            blame_lines.append("summary msg")
            blame_lines.append(f"\tline {i}")
        blame_raw = "\n".join(blame_lines) + "\n"

        call_count = {"n": 0}
        def llm(prompt):
            call_count["n"] += 1
            return "explained"

        analyzer = AIBlameAnalyzer(
            project_root="/fake",
            llm_callback=llm,
            max_entries=5,
        )
        with patch("lidco.git.ai_blame._run_git", return_value=blame_raw):
            entries = analyzer.analyze_file("foo.py")

        # max_entries=5 limits LLM calls to ≤5
        assert call_count["n"] <= 5
