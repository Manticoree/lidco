"""Tests for AutomationRunner (Task 724)."""
from __future__ import annotations

import unittest

from lidco.scheduler.trigger_registry import AutomationTrigger, AutomationTriggerRegistry
from lidco.scheduler.automation_runner import AutomationRunner, RunRecord, RunSummary


def _make_trigger(name="t1", trigger_type="cron", template="Do {{title}}", **kw):
    defaults = dict(config={}, instructions_template=template, output_type="log", memory_key="", enabled=True)
    defaults.update(kw)
    return AutomationTrigger(name=name, trigger_type=trigger_type, **defaults)


class TestAutomationRunner(unittest.TestCase):
    def setUp(self):
        self.reg = AutomationTriggerRegistry()
        self.agent_calls = []

        def mock_agent(prompt):
            self.agent_calls.append(prompt)
            return f"result:{prompt[:20]}"

        self.runner = AutomationRunner(self.reg, agent_fn=mock_agent)

    # -- basic run ----------------------------------------------------------

    def test_run_single_trigger(self):
        self.reg.register(_make_trigger("t1", "cron"))
        summary = self.runner.run("cron", {"schedule": "daily"})
        self.assertEqual(summary.triggered, 1)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(summary.failed, 0)

    def test_run_no_matching_triggers(self):
        self.reg.register(_make_trigger("t1", "cron"))
        summary = self.runner.run("slack", {})
        self.assertEqual(summary.triggered, 0)
        self.assertEqual(summary.records, [])

    def test_run_multiple_triggers(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.reg.register(_make_trigger("t2", "cron"))
        summary = self.runner.run("cron", {})
        self.assertEqual(summary.triggered, 2)

    def test_run_calls_agent_fn(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.runner.run("cron", {})
        self.assertEqual(len(self.agent_calls), 1)

    def test_run_renders_template(self):
        self.reg.register(_make_trigger("t1", "github_pr", template="Review PR {{title}}"))
        self.runner.run("github_pr", {"number": 1, "title": "My PR", "body": ""})
        self.assertIn("Review PR My PR", self.agent_calls[0])

    # -- agent failure ------------------------------------------------------

    def test_agent_failure_recorded(self):
        def failing_agent(prompt):
            raise RuntimeError("boom")

        runner = AutomationRunner(self.reg, agent_fn=failing_agent)
        self.reg.register(_make_trigger("t1", "cron"))
        summary = runner.run("cron", {})
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.succeeded, 0)
        self.assertIn("boom", summary.records[0].error)

    def test_agent_failure_success_false(self):
        def failing_agent(prompt):
            raise ValueError("bad")

        runner = AutomationRunner(self.reg, agent_fn=failing_agent)
        self.reg.register(_make_trigger("t1", "cron"))
        summary = runner.run("cron", {})
        self.assertFalse(summary.records[0].success)

    # -- no agent -----------------------------------------------------------

    def test_no_agent_fn(self):
        runner = AutomationRunner(self.reg, agent_fn=None)
        self.reg.register(_make_trigger("t1", "cron"))
        summary = runner.run("cron", {})
        self.assertEqual(summary.triggered, 1)
        self.assertIn("no agent", summary.records[0].output)

    # -- memory -------------------------------------------------------------

    def test_memory_stored_on_success(self):
        mem = {}
        runner = AutomationRunner(self.reg, agent_fn=lambda p: "answer", memory_store=mem)
        self.reg.register(_make_trigger("t1", "cron", memory_key="mk"))
        runner.run("cron", {})
        self.assertEqual(mem["mk"], "answer")

    def test_memory_prepended_on_next_run(self):
        mem = {"mk": "previous answer"}
        calls = []
        runner = AutomationRunner(self.reg, agent_fn=lambda p: (calls.append(p), "new")[1], memory_store=mem)
        self.reg.register(_make_trigger("t1", "cron", memory_key="mk"))
        runner.run("cron", {})
        self.assertIn("previous answer", calls[0])

    def test_memory_not_stored_on_failure(self):
        mem = {}

        def fail(p):
            raise RuntimeError("fail")

        runner = AutomationRunner(self.reg, agent_fn=fail, memory_store=mem)
        self.reg.register(_make_trigger("t1", "cron", memory_key="mk"))
        runner.run("cron", {})
        self.assertNotIn("mk", mem)

    def test_memory_empty_key_no_store(self):
        mem = {}
        runner = AutomationRunner(self.reg, agent_fn=lambda p: "res", memory_store=mem)
        self.reg.register(_make_trigger("t1", "cron", memory_key=""))
        runner.run("cron", {})
        self.assertEqual(len(mem), 0)

    # -- history ------------------------------------------------------------

    def test_history_empty_initially(self):
        self.assertEqual(self.runner.get_history(), [])

    def test_history_populated_after_run(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.runner.run("cron", {})
        hist = self.runner.get_history()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0].trigger_name, "t1")

    def test_history_limit(self):
        self.reg.register(_make_trigger("t1", "cron"))
        for _ in range(10):
            self.runner.run("cron", {})
        self.assertEqual(len(self.runner.get_history(limit=3)), 3)

    def test_history_accumulates(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.runner.run("cron", {})
        self.runner.run("cron", {})
        self.assertEqual(len(self.runner.get_history(limit=100)), 2)

    def test_clear_history(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.runner.run("cron", {})
        self.runner.clear_history()
        self.assertEqual(self.runner.get_history(), [])

    # -- RunRecord / RunSummary fields --------------------------------------

    def test_run_record_has_id(self):
        self.reg.register(_make_trigger("t1", "cron"))
        summary = self.runner.run("cron", {})
        self.assertTrue(len(summary.records[0].id) > 0)

    def test_run_record_has_timestamp(self):
        self.reg.register(_make_trigger("t1", "cron"))
        summary = self.runner.run("cron", {})
        self.assertIn("T", summary.records[0].timestamp)

    def test_run_record_input_is_rendered(self):
        self.reg.register(_make_trigger("t1", "github_pr", template="Fix {{title}}"))
        summary = self.runner.run("github_pr", {"number": 1, "title": "Bug"})
        self.assertEqual(summary.records[0].input, "Fix Bug")

    def test_run_summary_counts(self):
        def sometimes_fail(p):
            if "t2" in p:
                raise RuntimeError("fail")
            return "ok"

        runner = AutomationRunner(self.reg, agent_fn=sometimes_fail)
        self.reg.register(_make_trigger("t1", "cron", template="t1"))
        self.reg.register(_make_trigger("t2", "cron", template="t2"))
        summary = runner.run("cron", {})
        self.assertEqual(summary.triggered, 2)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(summary.failed, 1)

    # -- disabled triggers skipped ------------------------------------------

    def test_disabled_triggers_not_run(self):
        self.reg.register(_make_trigger("t1", "cron"))
        self.reg.disable("t1")
        summary = self.runner.run("cron", {})
        self.assertEqual(summary.triggered, 0)

    # -- default memory_store -----------------------------------------------

    def test_default_memory_store(self):
        runner = AutomationRunner(self.reg, agent_fn=lambda p: "res")
        self.reg.register(_make_trigger("t1", "cron", memory_key="mk"))
        runner.run("cron", {})
        # Should not raise - internal store is used


if __name__ == "__main__":
    unittest.main()
