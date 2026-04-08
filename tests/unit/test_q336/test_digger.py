"""Tests for lidco.archaeology.digger — HistoryDigger."""

from __future__ import annotations

import unittest

from lidco.archaeology.digger import (
    CommitInfo,
    DesignDecision,
    EvolutionTimeline,
    HistoryDigger,
)


class TestCommitInfo(unittest.TestCase):
    def test_short_sha(self) -> None:
        c = CommitInfo(sha="abcdef1234567890", author="dev", date="2024-01-01", message="init")
        self.assertEqual(c.short_sha(), "abcdef1")

    def test_short_sha_short_input(self) -> None:
        c = CommitInfo(sha="abc", author="dev", date="2024-01-01", message="init")
        self.assertEqual(c.short_sha(), "abc")

    def test_files_changed_default(self) -> None:
        c = CommitInfo(sha="a" * 40, author="dev", date="2024-01-01", message="m")
        self.assertEqual(c.files_changed, ())

    def test_frozen(self) -> None:
        c = CommitInfo(sha="a", author="dev", date="d", message="m")
        with self.assertRaises(AttributeError):
            c.sha = "b"  # type: ignore[misc]


class TestDesignDecision(unittest.TestCase):
    def test_high_confidence_true(self) -> None:
        d = DesignDecision(commit_sha="a", date="d", summary="s", category="api", confidence=0.8)
        self.assertTrue(d.is_high_confidence())

    def test_high_confidence_false(self) -> None:
        d = DesignDecision(commit_sha="a", date="d", summary="s", category="api", confidence=0.5)
        self.assertFalse(d.is_high_confidence())

    def test_high_confidence_boundary(self) -> None:
        d = DesignDecision(commit_sha="a", date="d", summary="s", category="api", confidence=0.7)
        self.assertTrue(d.is_high_confidence())


class TestEvolutionTimeline(unittest.TestCase):
    def test_span_empty(self) -> None:
        tl = EvolutionTimeline(target="foo.py")
        self.assertEqual(tl.span, 0)

    def test_span_with_entries(self) -> None:
        entries = [
            CommitInfo(sha="a" * 7, author="dev", date="2024-01-01", message="first"),
            CommitInfo(sha="b" * 7, author="dev", date="2024-01-02", message="second"),
        ]
        tl = EvolutionTimeline(target="foo.py", entries=entries)
        self.assertEqual(tl.span, 2)

    def test_summary_includes_target(self) -> None:
        tl = EvolutionTimeline(target="main.py")
        self.assertIn("main.py", tl.summary())

    def test_summary_includes_decisions(self) -> None:
        d = DesignDecision(commit_sha="a", date="d", summary="refactored", category="refactor", confidence=0.8)
        tl = EvolutionTimeline(target="x", decisions=[d])
        s = tl.summary()
        self.assertIn("[HIGH]", s)
        self.assertIn("refactored", s)


class TestHistoryDigger(unittest.TestCase):
    def _make_commits(self) -> list[CommitInfo]:
        return [
            CommitInfo(
                sha="c3" + "0" * 38,
                author="alice",
                date="2024-03-01",
                message="Refactor authentication module",
                files_changed=("auth.py", "utils.py"),
            ),
            CommitInfo(
                sha="c2" + "0" * 38,
                author="bob",
                date="2024-02-01",
                message="Add API endpoint for users",
                files_changed=("api.py", "users.py"),
            ),
            CommitInfo(
                sha="c1" + "0" * 38,
                author="alice",
                date="2024-01-01",
                message="Initial commit with auth.py",
                files_changed=("auth.py",),
            ),
        ]

    def test_commit_count(self) -> None:
        digger = HistoryDigger(self._make_commits())
        self.assertEqual(digger.commit_count, 3)

    def test_commit_count_empty(self) -> None:
        digger = HistoryDigger()
        self.assertEqual(digger.commit_count, 0)

    def test_add_commit(self) -> None:
        digger = HistoryDigger()
        digger.add_commit(CommitInfo(sha="x", author="a", date="d", message="m"))
        self.assertEqual(digger.commit_count, 1)

    def test_timeline_for_file(self) -> None:
        digger = HistoryDigger(self._make_commits())
        tl = digger.timeline_for("auth.py")
        self.assertEqual(tl.span, 2)
        self.assertEqual(tl.target, "auth.py")

    def test_timeline_for_keyword_in_message(self) -> None:
        digger = HistoryDigger(self._make_commits())
        tl = digger.timeline_for("API")
        self.assertEqual(tl.span, 1)

    def test_timeline_for_no_match(self) -> None:
        digger = HistoryDigger(self._make_commits())
        tl = digger.timeline_for("nonexistent")
        self.assertEqual(tl.span, 0)

    def test_find_decisions(self) -> None:
        digger = HistoryDigger(self._make_commits())
        decisions = digger.find_decisions()
        self.assertTrue(len(decisions) > 0)
        categories = {d.category for d in decisions}
        self.assertIn("architecture", categories)  # "Refactor" matches

    def test_original_intent_found(self) -> None:
        digger = HistoryDigger(self._make_commits())
        intent = digger.original_intent("auth.py")
        self.assertIn("Initial commit", intent)

    def test_original_intent_not_found(self) -> None:
        digger = HistoryDigger(self._make_commits())
        intent = digger.original_intent("nope.py")
        self.assertIn("No history found", intent)

    def test_hot_files(self) -> None:
        digger = HistoryDigger(self._make_commits())
        hot = digger.hot_files(top_n=3)
        self.assertTrue(len(hot) > 0)
        # auth.py appears in 2 commits
        top_file, top_count = hot[0]
        self.assertEqual(top_file, "auth.py")
        self.assertEqual(top_count, 2)

    def test_hot_files_top_n(self) -> None:
        digger = HistoryDigger(self._make_commits())
        hot = digger.hot_files(top_n=1)
        self.assertEqual(len(hot), 1)

    def test_hot_files_empty(self) -> None:
        digger = HistoryDigger()
        self.assertEqual(digger.hot_files(), [])

    def test_decision_confidence_scaling(self) -> None:
        # Commit that matches multiple patterns should have higher confidence
        c = CommitInfo(
            sha="x" * 40,
            author="dev",
            date="d",
            message="Refactor and restructure API architecture",
        )
        digger = HistoryDigger([c])
        decisions = digger.find_decisions()
        arch_decisions = [d for d in decisions if d.category == "architecture"]
        self.assertTrue(len(arch_decisions) > 0)
        # Multiple matches -> higher confidence
        self.assertGreater(arch_decisions[0].confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
