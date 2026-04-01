"""Tests for agents.summarizer — AgentAction, AgentSummary, AgentSummarizer."""
from __future__ import annotations

import unittest

from lidco.agents.summarizer import AgentAction, AgentSummary, AgentSummarizer


class TestAgentAction(unittest.TestCase):
    def test_frozen(self):
        a = AgentAction(action_type="edit", target="file.py", timestamp="t")
        with self.assertRaises(AttributeError):
            a.action_type = "x"  # type: ignore[misc]

    def test_fields(self):
        a = AgentAction("create", "new.py", "2026-01-01")
        self.assertEqual(a.action_type, "create")
        self.assertEqual(a.target, "new.py")
        self.assertEqual(a.timestamp, "2026-01-01")

    def test_equality(self):
        a = AgentAction("edit", "f", "t")
        b = AgentAction("edit", "f", "t")
        self.assertEqual(a, b)


class TestAgentSummary(unittest.TestCase):
    def test_frozen(self):
        s = AgentSummary(
            agent_name="bot",
            actions=(),
            files_modified=(),
            duration_ms=100,
            cost=0.01,
            key_decisions=(),
        )
        with self.assertRaises(AttributeError):
            s.agent_name = "x"  # type: ignore[misc]

    def test_fields(self):
        s = AgentSummary("bot", (), ("a.py",), 50, 0.05, ("chose X",))
        self.assertEqual(s.agent_name, "bot")
        self.assertEqual(s.files_modified, ("a.py",))
        self.assertEqual(s.duration_ms, 50)
        self.assertAlmostEqual(s.cost, 0.05)
        self.assertEqual(s.key_decisions, ("chose X",))


class TestAgentSummarizer(unittest.TestCase):
    def test_record_action_returns_new(self):
        s1 = AgentSummarizer(agent_name="bot")
        action = AgentAction("edit", "file.py", "t")
        s2 = s1.record_action(action)
        self.assertIsNot(s1, s2)

    def test_summarize_empty(self):
        s = AgentSummarizer(agent_name="bot")
        summary = s.summarize()
        self.assertEqual(summary.agent_name, "bot")
        self.assertEqual(summary.actions, ())
        self.assertEqual(summary.files_modified, ())

    def test_summarize_with_actions(self):
        s = AgentSummarizer(agent_name="bot")
        s = s.record_action(AgentAction("edit", "a.py", "t1"))
        s = s.record_action(AgentAction("create", "b.py", "t2"))
        s = s.record_action(AgentAction("read", "c.py", "t3"))
        summary = s.summarize()
        self.assertEqual(len(summary.actions), 3)
        # Only edit/create are counted as file modifications
        self.assertIn("a.py", summary.files_modified)
        self.assertIn("b.py", summary.files_modified)
        self.assertNotIn("c.py", summary.files_modified)

    def test_summarize_key_decisions(self):
        s = AgentSummarizer(agent_name="bot")
        s = s.record_action(AgentAction("decide", "use strategy A", "t"))
        s = s.record_action(AgentAction("approve", "PR #42", "t"))
        summary = s.summarize()
        self.assertEqual(len(summary.key_decisions), 2)
        self.assertIn("use strategy A", summary.key_decisions)

    def test_format_markdown(self):
        s = AgentSummarizer(agent_name="bot")
        s = s.record_action(AgentAction("edit", "file.py", "t"))
        md = s.format_markdown()
        self.assertIn("# Agent Summary: bot", md)
        self.assertIn("file.py", md)

    def test_format_markdown_empty(self):
        s = AgentSummarizer(agent_name="bot")
        md = s.format_markdown()
        self.assertIn("bot", md)
        self.assertIn("Actions", md)

    def test_files_modified_sorted(self):
        s = AgentSummarizer()
        s = s.record_action(AgentAction("edit", "z.py", "t"))
        s = s.record_action(AgentAction("edit", "a.py", "t"))
        summary = s.summarize()
        self.assertEqual(summary.files_modified, ("a.py", "z.py"))

    def test_files_modified_deduped(self):
        s = AgentSummarizer()
        s = s.record_action(AgentAction("edit", "a.py", "t1"))
        s = s.record_action(AgentAction("edit", "a.py", "t2"))
        summary = s.summarize()
        self.assertEqual(summary.files_modified, ("a.py",))

    def test_duration_ms_positive(self):
        s = AgentSummarizer()
        summary = s.summarize()
        self.assertGreaterEqual(summary.duration_ms, 0)

    def test_default_agent_name(self):
        s = AgentSummarizer()
        summary = s.summarize()
        self.assertEqual(summary.agent_name, "agent")

    def test_immutability_chain(self):
        s1 = AgentSummarizer(agent_name="bot")
        s2 = s1.record_action(AgentAction("edit", "a.py", "t"))
        s3 = s2.record_action(AgentAction("edit", "b.py", "t"))
        self.assertEqual(len(s1.summarize().actions), 0)
        self.assertEqual(len(s2.summarize().actions), 1)
        self.assertEqual(len(s3.summarize().actions), 2)

    def test_format_markdown_with_decisions(self):
        s = AgentSummarizer(agent_name="bot")
        s = s.record_action(AgentAction("decide", "use X", "t"))
        md = s.format_markdown()
        self.assertIn("Key Decisions", md)

    def test_delete_action_counts_as_file_modified(self):
        s = AgentSummarizer()
        s = s.record_action(AgentAction("delete", "old.py", "t"))
        summary = s.summarize()
        self.assertIn("old.py", summary.files_modified)

    def test_write_action_counts_as_file_modified(self):
        s = AgentSummarizer()
        s = s.record_action(AgentAction("write", "out.py", "t"))
        summary = s.summarize()
        self.assertIn("out.py", summary.files_modified)

    def test_reject_action_counts_as_decision(self):
        s = AgentSummarizer()
        s = s.record_action(AgentAction("reject", "bad approach", "t"))
        summary = s.summarize()
        self.assertIn("bad approach", summary.key_decisions)


class TestAgentSummarizerAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.agents import summarizer

        self.assertIn("AgentAction", summarizer.__all__)
        self.assertIn("AgentSummary", summarizer.__all__)
        self.assertIn("AgentSummarizer", summarizer.__all__)


if __name__ == "__main__":
    unittest.main()
