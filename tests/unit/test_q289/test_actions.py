"""Tests for lidco.github.actions — ActionsMonitor."""
from __future__ import annotations

import unittest

from lidco.github.actions import ActionsMonitor, Run


class TestActionsMonitor(unittest.TestCase):
    def setUp(self):
        self.mon = ActionsMonitor()

    # -- list_runs --------------------------------------------------------

    def test_list_runs_empty(self):
        self.assertEqual(self.mon.list_runs("owner/repo"), [])

    def test_list_runs_returns_matching(self):
        self.mon._add_run("owner/repo")
        self.mon._add_run("other/repo")
        runs = self.mon.list_runs("owner/repo")
        self.assertEqual(len(runs), 1)

    def test_list_runs_empty_repo_raises(self):
        with self.assertRaises(ValueError):
            self.mon.list_runs("")

    # -- get_run ----------------------------------------------------------

    def test_get_run_found(self):
        r = self.mon._add_run("r")
        self.assertEqual(self.mon.get_run(r.id), r)

    def test_get_run_not_found(self):
        self.assertIsNone(self.mon.get_run(999))

    # -- parse_logs -------------------------------------------------------

    def test_parse_logs_strips_and_filters(self):
        r = self.mon._add_run("r", logs=["  info  ", "", "done"])
        parsed = self.mon.parse_logs(r.id)
        self.assertEqual(parsed, ["info", "done"])

    def test_parse_logs_missing_run(self):
        self.assertEqual(self.mon.parse_logs(999), [])

    # -- detect_failures --------------------------------------------------

    def test_detect_failures_finds_errors(self):
        r = self.mon._add_run("r", logs=["OK", "Error: compile", "FATAL crash", "info"])
        failures = self.mon.detect_failures(r.id)
        self.assertEqual(len(failures), 2)

    def test_detect_failures_none_found(self):
        r = self.mon._add_run("r", logs=["OK", "passed"])
        self.assertEqual(self.mon.detect_failures(r.id), [])

    def test_detect_failures_missing_run(self):
        self.assertEqual(self.mon.detect_failures(999), [])

    # -- retrigger --------------------------------------------------------

    def test_retrigger_success(self):
        r = self.mon._add_run("r", status="completed", conclusion="failure")
        self.assertTrue(self.mon.retrigger(r.id))
        self.assertEqual(r.status, "queued")
        self.assertIsNone(r.conclusion)

    def test_retrigger_missing(self):
        self.assertFalse(self.mon.retrigger(999))

    # -- Run dataclass ----------------------------------------------------

    def test_run_dataclass_fields(self):
        r = Run(id=1, repo="x", status="completed", conclusion="success")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.conclusion, "success")


if __name__ == "__main__":
    unittest.main()
