"""Tests for Q300 CLI commands (Q300)."""
import asyncio
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _run(coro):
    return asyncio.run(coro)


class TestQ300Commands(unittest.TestCase):

    def _registry(self):
        from lidco.cli.commands.q300_cmds import register_q300_commands
        reg = _FakeRegistry()
        register_q300_commands(reg)
        return reg

    def test_all_commands_registered(self):
        reg = self._registry()
        expected = {"pr-description", "pr-reviewer", "pr-checklist", "pr-status"}
        self.assertEqual(set(reg.commands.keys()), expected)

    # -- /pr-description --
    def test_pr_description_no_args(self):
        reg = self._registry()
        result = _run(reg.commands["pr-description"](""))
        self.assertIn("Usage", result)

    def test_pr_description_with_diff(self):
        reg = self._registry()
        result = _run(reg.commands["pr-description"]("--- a/foo.py +++ b/foo.py +new_line"))
        self.assertIn("Summary", result)

    # -- /pr-reviewer --
    def test_pr_reviewer_no_args(self):
        reg = self._registry()
        result = _run(reg.commands["pr-reviewer"](""))
        self.assertIn("Usage", result)

    def test_pr_reviewer_suggest_empty(self):
        reg = self._registry()
        result = _run(reg.commands["pr-reviewer"]("suggest src/foo.py"))
        self.assertIn("No reviewers", result)

    def test_pr_reviewer_add_owner(self):
        reg = self._registry()
        result = _run(reg.commands["pr-reviewer"]("add-owner '*.py' alice"))
        self.assertIn("Owner added", result)

    def test_pr_reviewer_activity(self):
        reg = self._registry()
        result = _run(reg.commands["pr-reviewer"]("activity bob"))
        self.assertIn("0 event(s)", result)

    # -- /pr-checklist --
    def test_pr_checklist_no_args(self):
        reg = self._registry()
        result = _run(reg.commands["pr-checklist"](""))
        self.assertIn("Usage", result)

    def test_pr_checklist_generate(self):
        reg = self._registry()
        result = _run(reg.commands["pr-checklist"]("generate feature"))
        self.assertIn("Checklist", result)

    def test_pr_checklist_security(self):
        reg = self._registry()
        result = _run(reg.commands["pr-checklist"]("security password=foo"))
        self.assertIn("password", result)

    def test_pr_checklist_deploy_no_match(self):
        reg = self._registry()
        result = _run(reg.commands["pr-checklist"]("deploy foo.py"))
        self.assertIn("No deployment notes", result)

    # -- /pr-status --
    def test_pr_status_no_args(self):
        reg = self._registry()
        result = _run(reg.commands["pr-status"](""))
        self.assertIn("Usage", result)

    def test_pr_status_track(self):
        reg = self._registry()
        result = _run(reg.commands["pr-status"]("track PR-42"))
        self.assertIn("PR-42", result)

    def test_pr_status_ci(self):
        reg = self._registry()
        _run(reg.commands["pr-status"]("track PR-1"))
        result = _run(reg.commands["pr-status"]("ci PR-1 passed"))
        self.assertIn("passed", result)

    def test_pr_status_review(self):
        reg = self._registry()
        _run(reg.commands["pr-status"]("track PR-1"))
        result = _run(reg.commands["pr-status"]("review PR-1 alice approve"))
        self.assertIn("approved", result)

    def test_pr_status_check(self):
        reg = self._registry()
        _run(reg.commands["pr-status"]("track PR-1"))
        result = _run(reg.commands["pr-status"]("check PR-1"))
        self.assertIn("Ready to merge", result)

    def test_pr_status_list(self):
        reg = self._registry()
        _run(reg.commands["pr-status"]("track PR-1"))
        result = _run(reg.commands["pr-status"]("list"))
        self.assertIn("PR-1", result)


if __name__ == "__main__":
    unittest.main()
