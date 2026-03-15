"""Tests for CommitAnalyzer — Task 335."""

from __future__ import annotations

import pytest

from lidco.analysis.commit_analyzer import CommitAnalyzer, CommitRecord, CommitStats


class TestCommitRecord:
    def test_frozen(self):
        r = CommitRecord(hash="abc", message="fix: bug", author="alice")
        with pytest.raises((AttributeError, TypeError)):
            r.hash = "xyz"  # type: ignore[misc]

    def test_default_files_empty(self):
        r = CommitRecord(hash="a", message="m", author="x")
        assert r.files_changed == ()

    def test_with_files(self):
        r = CommitRecord(hash="a", message="m", author="x", files_changed=("f.py",))
        assert "f.py" in r.files_changed


class TestScoreMessage:
    def setup_method(self):
        self.a = CommitAnalyzer()

    def test_conventional_feat(self):
        assert self.a.score_message("feat: add login") == 1.0

    def test_conventional_fix(self):
        assert self.a.score_message("fix(auth): null pointer") == 1.0

    def test_conventional_breaking(self):
        assert self.a.score_message("feat!: remove old API") == 1.0

    def test_conventional_with_scope(self):
        assert self.a.score_message("refactor(cli): simplify handler") == 1.0

    def test_non_conventional_non_empty(self):
        assert self.a.score_message("Updated readme") == 0.5

    def test_empty_string(self):
        assert self.a.score_message("") == 0.0

    def test_whitespace_only(self):
        assert self.a.score_message("   ") == 0.0

    def test_all_types_score_1(self):
        types = ["feat", "fix", "refactor", "docs", "test",
                 "chore", "perf", "ci", "build", "style", "revert"]
        for t in types:
            assert self.a.score_message(f"{t}: something") == 1.0


class TestAnalyze:
    def setup_method(self):
        self.a = CommitAnalyzer()

    def test_empty_returns_zero(self):
        stats = self.a.analyze([])
        assert stats.total_commits == 0
        assert stats.authors == {}
        assert stats.churn_files == []
        assert stats.message_quality == 0.0

    def test_single_commit(self):
        r = CommitRecord(hash="a", message="feat: x", author="alice",
                         files_changed=("main.py",))
        stats = self.a.analyze([r])
        assert stats.total_commits == 1
        assert stats.authors["alice"] == 1
        assert stats.churn_files[0] == ("main.py", 1)
        assert stats.message_quality == 1.0

    def test_author_counts(self):
        records = [
            CommitRecord(hash="a", message="x", author="alice"),
            CommitRecord(hash="b", message="y", author="bob"),
            CommitRecord(hash="c", message="z", author="alice"),
        ]
        stats = self.a.analyze(records)
        assert stats.authors["alice"] == 2
        assert stats.authors["bob"] == 1

    def test_churn_files_sorted_desc(self):
        records = [
            CommitRecord(hash="a", message="x", author="a",
                         files_changed=("a.py", "b.py")),
            CommitRecord(hash="b", message="y", author="a",
                         files_changed=("a.py",)),
        ]
        stats = self.a.analyze(records)
        assert stats.churn_files[0] == ("a.py", 2)
        assert stats.churn_files[1] == ("b.py", 1)

    def test_message_quality_average(self):
        records = [
            CommitRecord(hash="a", message="feat: good", author="a"),  # 1.0
            CommitRecord(hash="b", message="bad msg", author="a"),      # 0.5
        ]
        stats = self.a.analyze(records)
        assert stats.message_quality == pytest.approx(0.75)


class TestParseGitLog:
    def setup_method(self):
        self.a = CommitAnalyzer()

    def test_empty_returns_empty(self):
        assert self.a.parse_git_log("") == []

    def test_single_commit(self):
        log = (
            "COMMIT:abc123\n"
            "AUTHOR:Alice\n"
            "DATE:2024-01-01T00:00:00Z\n"
            "MESSAGE:feat: initial\n"
            "FILES:\n"
            "main.py\n"
        )
        records = self.a.parse_git_log(log)
        assert len(records) == 1
        assert records[0].hash == "abc123"
        assert records[0].author == "Alice"
        assert records[0].message == "feat: initial"
        assert "main.py" in records[0].files_changed

    def test_multiple_commits(self):
        log = (
            "COMMIT:aaa\nAUTHOR:A\nDATE:d1\nMESSAGE:m1\nFILES:\nf1.py\n\n"
            "COMMIT:bbb\nAUTHOR:B\nDATE:d2\nMESSAGE:m2\nFILES:\nf2.py\n"
        )
        records = self.a.parse_git_log(log)
        assert len(records) == 2
        assert records[0].hash == "aaa"
        assert records[1].hash == "bbb"

    def test_commit_no_files(self):
        log = "COMMIT:xyz\nAUTHOR:X\nDATE:d\nMESSAGE:fix: thing\nFILES:\n"
        records = self.a.parse_git_log(log)
        assert records[0].files_changed == ()
