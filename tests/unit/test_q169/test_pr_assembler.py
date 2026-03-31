"""Tests for PRAssembler."""
from __future__ import annotations

import unittest

from lidco.cloud.agent_spawner import AgentHandle
from lidco.cloud.status_tracker import AgentLog
from lidco.cloud.pr_assembler import PRAssembler, PRDraft


class TestPRDraft(unittest.TestCase):
    def test_defaults(self):
        d = PRDraft(title="t", body="b", branch="br", base_branch="main")
        self.assertEqual(d.files_changed, [])
        self.assertEqual(d.additions, 0)
        self.assertEqual(d.deletions, 0)


class TestPRAssemblerAssemble(unittest.TestCase):
    def setUp(self):
        self.assembler = PRAssembler()

    def _handle(self, prompt="Fix bug", branch="agent/fix-bug"):
        return AgentHandle(
            agent_id="abc",
            prompt=prompt,
            model="gpt-4",
            status="completed",
            created_at=1.0,
            branch_name=branch,
        )

    def _log(self, output="done", diff="", entries=None):
        return AgentLog(
            agent_id="abc",
            entries=entries or [],
            output=output,
            diff=diff,
            started_at=1.0,
            finished_at=2.0,
        )

    def test_assemble_returns_draft(self):
        draft = self.assembler.assemble(self._handle(), self._log())
        self.assertIsInstance(draft, PRDraft)

    def test_assemble_branch(self):
        draft = self.assembler.assemble(self._handle(), self._log())
        self.assertEqual(draft.branch, "agent/fix-bug")
        self.assertEqual(draft.base_branch, "main")

    def test_assemble_with_diff(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n+new line\n-old line"
        draft = self.assembler.assemble(self._handle(), self._log(diff=diff))
        self.assertEqual(draft.additions, 1)
        self.assertEqual(draft.deletions, 1)
        self.assertIn("foo.py", draft.files_changed)

    def test_assemble_fallback_branch(self):
        h = self._handle(branch=None)
        draft = self.assembler.assemble(h, self._log())
        self.assertIn("abc", draft.branch)


class TestGenerateTitle(unittest.TestCase):
    def setUp(self):
        self.assembler = PRAssembler()

    def test_short_prompt(self):
        title = self.assembler.generate_title("Fix login", [])
        self.assertEqual(title, "Fix login")

    def test_long_prompt_truncated(self):
        title = self.assembler.generate_title("A" * 100, [])
        self.assertLessEqual(len(title), 70)
        self.assertTrue(title.endswith("..."))


class TestGenerateBody(unittest.TestCase):
    def setUp(self):
        self.assembler = PRAssembler()

    def test_body_contains_summary(self):
        log = AgentLog(agent_id="x")
        body = self.assembler.generate_body("Fix bug", log)
        self.assertIn("## Summary", body)
        self.assertIn("Fix bug", body)

    def test_body_contains_test_plan(self):
        log = AgentLog(agent_id="x")
        body = self.assembler.generate_body("Fix", log)
        self.assertIn("## Test Plan", body)

    def test_body_includes_log_entries(self):
        log = AgentLog(agent_id="x", entries=["step1", "step2"])
        body = self.assembler.generate_body("Fix", log)
        self.assertIn("step1", body)

    def test_body_includes_output(self):
        log = AgentLog(agent_id="x", output="result text")
        body = self.assembler.generate_body("Fix", log)
        self.assertIn("result text", body)

    def test_body_includes_files_changed(self):
        log = AgentLog(agent_id="x", diff="+++ b/src/foo.py\n+line")
        body = self.assembler.generate_body("Fix", log)
        self.assertIn("src/foo.py", body)


class TestCountChanges(unittest.TestCase):
    def setUp(self):
        self.assembler = PRAssembler()

    def test_empty_diff(self):
        self.assertEqual(self.assembler.count_changes(""), (0, 0))

    def test_additions_only(self):
        diff = "+++ b/f.py\n+line1\n+line2"
        adds, dels = self.assembler.count_changes(diff)
        self.assertEqual(adds, 2)
        self.assertEqual(dels, 0)

    def test_deletions_only(self):
        diff = "--- a/f.py\n-line1"
        adds, dels = self.assembler.count_changes(diff)
        self.assertEqual(adds, 0)
        self.assertEqual(dels, 1)

    def test_mixed(self):
        diff = "+++ b/f.py\n--- a/f.py\n+add\n-del\n+add2"
        adds, dels = self.assembler.count_changes(diff)
        self.assertEqual(adds, 2)
        self.assertEqual(dels, 1)

    def test_header_lines_excluded(self):
        diff = "+++ b/f.py\n--- a/f.py\n@@hunk\n+real"
        adds, dels = self.assembler.count_changes(diff)
        self.assertEqual(adds, 1)
        self.assertEqual(dels, 0)


if __name__ == "__main__":
    unittest.main()
