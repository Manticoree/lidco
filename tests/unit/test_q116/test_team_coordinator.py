"""Tests for TeamCoordinator (Task 714)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from lidco.agents.team_coordinator import CoordinationResult, TeamCoordinator
from lidco.agents.team_registry import AgentTeam


class TestCoordinationResult(unittest.TestCase):
    def test_defaults(self):
        cr = CoordinationResult(prompt="test", tasks_created=0)
        self.assertEqual(cr.prompt, "test")
        self.assertEqual(cr.tasks_created, 0)
        self.assertEqual(cr.outputs, {})
        self.assertFalse(cr.timed_out)
        self.assertEqual(cr.errors, [])

    def test_with_outputs(self):
        cr = CoordinationResult(prompt="p", tasks_created=2, outputs={"a": "r1", "b": "r2"})
        self.assertEqual(len(cr.outputs), 2)

    def test_timed_out_flag(self):
        cr = CoordinationResult(prompt="p", tasks_created=1, timed_out=True)
        self.assertTrue(cr.timed_out)


class TestTeamCoordinator(unittest.TestCase):
    def test_init_defaults(self):
        tc = TeamCoordinator()
        self.assertIsNone(tc.team)
        self.assertIsNone(tc.mailbox)

    def test_init_with_team(self):
        team = AgentTeam(name="t", roles={})
        tc = TeamCoordinator(team=team)
        self.assertIs(tc.team, team)

    def test_run_no_teammates(self):
        tc = TeamCoordinator()
        result = tc.run("do something", {})
        self.assertEqual(result.tasks_created, 1)
        self.assertIn("(no teammates)", list(result.outputs.values()))

    def test_run_single_teammate(self):
        tc = TeamCoordinator()
        fns = {"dev": lambda t: f"done: {t}"}
        result = tc.run("build feature", fns)
        self.assertEqual(result.tasks_created, 1)
        self.assertEqual(len(result.outputs), 1)
        self.assertIn("done:", list(result.outputs.values())[0])

    def test_run_multiple_teammates(self):
        tc = TeamCoordinator()
        fns = {
            "dev": lambda t: "coded",
            "reviewer": lambda t: "reviewed",
        }
        result = tc.run("1. code it\n2. review it", fns)
        self.assertEqual(result.tasks_created, 2)
        self.assertEqual(len(result.outputs), 2)

    def test_run_error_in_teammate(self):
        tc = TeamCoordinator()
        fns = {"bad": lambda t: (_ for _ in ()).throw(ValueError("boom"))}

        def failing_fn(t):
            raise ValueError("boom")

        fns = {"bad": failing_fn}
        result = tc.run("do thing", fns)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("boom", result.errors[0])

    def test_run_timeout(self):
        tc = TeamCoordinator()

        def slow_fn(t):
            time.sleep(10)
            return "late"

        fns = {"slow": slow_fn}
        result = tc.run("hurry", fns, timeout_s=0.1)
        self.assertTrue(result.timed_out)

    def test_run_returns_coordination_result(self):
        tc = TeamCoordinator()
        result = tc.run("test", {"a": lambda t: "ok"})
        self.assertIsInstance(result, CoordinationResult)

    def test_run_preserves_prompt(self):
        tc = TeamCoordinator()
        result = tc.run("my prompt", {})
        self.assertEqual(result.prompt, "my prompt")


class TestSplitPrompt(unittest.TestCase):
    def setUp(self):
        self.tc = TeamCoordinator()

    def test_single_split(self):
        result = self.tc.split_prompt("hello world", 1)
        self.assertEqual(result, ["hello world"])

    def test_numbered_lines(self):
        prompt = "1. first task\n2. second task\n3. third task"
        result = self.tc.split_prompt(prompt, 3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "first task")
        self.assertEqual(result[1], "second task")

    def test_numbered_lines_more_than_n(self):
        prompt = "1. a\n2. b\n3. c\n4. d"
        result = self.tc.split_prompt(prompt, 2)
        self.assertEqual(len(result), 2)

    def test_sentence_split(self):
        prompt = "Do this first. Then do that. Finally wrap up."
        result = self.tc.split_prompt(prompt, 3)
        self.assertEqual(len(result), 3)

    def test_sentence_split_uneven(self):
        prompt = "A. B. C. D. E."
        result = self.tc.split_prompt(prompt, 2)
        self.assertEqual(len(result), 2)

    def test_n_zero_or_negative(self):
        result = self.tc.split_prompt("hello", 0)
        self.assertEqual(result, ["hello"])

    def test_single_sentence_padded(self):
        result = self.tc.split_prompt("just one", 3)
        self.assertEqual(len(result), 3)

    def test_numbered_with_parens(self):
        prompt = "1) alpha\n2) beta"
        result = self.tc.split_prompt(prompt, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "alpha")

    def test_empty_prompt(self):
        result = self.tc.split_prompt("", 1)
        self.assertEqual(result, [""])

    def test_split_returns_list(self):
        result = self.tc.split_prompt("abc", 2)
        self.assertIsInstance(result, list)

    def test_concurrent_run(self):
        """Multiple teammate functions run concurrently."""
        tc = TeamCoordinator()
        call_order = []

        def fn_a(t):
            call_order.append("a")
            return "a_done"

        def fn_b(t):
            call_order.append("b")
            return "b_done"

        fns = {"a": fn_a, "b": fn_b}
        result = tc.run("1. first\n2. second", fns)
        self.assertEqual(result.tasks_created, 2)
        self.assertEqual(len(result.outputs), 2)

    def test_run_with_team_object(self):
        team = AgentTeam(name="t", roles={"dev": "codes"})
        tc = TeamCoordinator(team=team, mailbox=MagicMock())
        result = tc.run("code it", {"dev": lambda t: "coded"})
        self.assertEqual(result.tasks_created, 1)

    def test_no_errors_on_success(self):
        tc = TeamCoordinator()
        result = tc.run("go", {"a": lambda t: "ok"})
        self.assertEqual(result.errors, [])

    def test_mixed_success_and_failure(self):
        tc = TeamCoordinator()

        def ok_fn(t):
            return "ok"

        def bad_fn(t):
            raise RuntimeError("fail")

        fns = {"ok": ok_fn, "bad": bad_fn}
        result = tc.run("1. a\n2. b", fns)
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(len(result.outputs) >= 1)


if __name__ == "__main__":
    unittest.main()
