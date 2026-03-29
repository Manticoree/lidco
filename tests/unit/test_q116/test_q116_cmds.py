"""Tests for Q116 CLI commands (Task 716)."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock

import lidco.cli.commands.q116_cmds as q116_cmds


def run(coro):
    return asyncio.run(coro)


class TestTeamCommands(unittest.TestCase):
    def setUp(self):
        q116_cmds._state.clear()
        self.registry = MagicMock()
        self.handler = None
        # Capture the registered handler
        def capture_register(cmd):
            self.handler = cmd.handler
        self.registry.register = capture_register
        q116_cmds.register(self.registry)

    def test_register_called(self):
        self.assertIsNotNone(self.handler)

    def test_create_team(self):
        roles = json.dumps({"dev": "writes code", "reviewer": "reviews"})
        result = run(self.handler(f"create myteam {roles}"))
        self.assertIn("myteam", result)
        self.assertIn("2 role(s)", result)

    def test_create_team_invalid_json(self):
        result = run(self.handler("create bad {not json}"))
        self.assertIn("Invalid JSON", result)

    def test_create_team_non_dict(self):
        result = run(self.handler('create bad ["list"]'))
        self.assertIn("must be a JSON object", result)

    def test_create_missing_args(self):
        result = run(self.handler("create"))
        self.assertIn("Usage", result)

    def test_assign_task(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("assign implement login"))
        self.assertIn("Task", result)
        self.assertIn("added", result)

    def test_assign_no_team(self):
        result = run(self.handler("assign do thing"))
        self.assertIn("No team created", result)

    def test_status_no_team(self):
        result = run(self.handler("status"))
        self.assertIn("No team created", result)

    def test_status_with_team(self):
        roles = json.dumps({"dev": "codes", "qa": "tests"})
        run(self.handler(f"create myteam {roles}"))
        result = run(self.handler("status"))
        self.assertIn("myteam", result)
        self.assertIn("dev", result)
        self.assertIn("qa", result)
        self.assertIn("Pending tasks: 0", result)

    def test_status_with_tasks(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        run(self.handler("assign task1"))
        result = run(self.handler("status"))
        self.assertIn("Pending tasks: 1", result)

    def test_challenge(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("challenge bug in auth module"))
        self.assertIn("Challenge issued", result)

    def test_challenge_no_team(self):
        result = run(self.handler("challenge something"))
        self.assertIn("No team created", result)

    def test_run_no_team(self):
        # Should still work (creates coordinator with no team)
        result = run(self.handler("run do something"))
        self.assertIn("Prompt", result)
        self.assertIn("Tasks", result)

    def test_run_with_team(self):
        roles = json.dumps({"dev": "codes", "qa": "tests"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("run 1. write code\n2. test code"))
        self.assertIn("Prompt", result)
        self.assertIn("Tasks", result)

    def test_run_missing_prompt(self):
        result = run(self.handler("run"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = run(self.handler("unknown"))
        self.assertIn("Usage", result)

    def test_empty_args(self):
        result = run(self.handler(""))
        self.assertIn("Usage", result)

    def test_create_single_role(self):
        roles = json.dumps({"solo": "does everything"})
        result = run(self.handler(f"create solo {roles}"))
        self.assertIn("1 role(s)", result)

    def test_assign_long_task(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("assign implement the entire authentication module with OAuth2"))
        self.assertIn("added", result)

    def test_create_overwrites_previous(self):
        roles1 = json.dumps({"dev": "codes"})
        roles2 = json.dumps({"qa": "tests"})
        run(self.handler(f"create t {roles1}"))
        run(self.handler(f"create t {roles2}"))
        result = run(self.handler("status"))
        self.assertIn("qa", result)

    def test_challenge_returns_id(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("challenge bad code"))
        # Should contain a hex id
        self.assertIn("Challenge issued:", result)

    def test_run_outputs_contain_results(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("run build feature"))
        self.assertIn("done:", result)

    def test_status_shows_roles(self):
        roles = json.dumps({"alpha": "a", "beta": "b", "gamma": "g"})
        run(self.handler(f"create t {roles}"))
        result = run(self.handler("status"))
        self.assertIn("alpha", result)
        self.assertIn("beta", result)
        self.assertIn("gamma", result)

    def test_create_empty_roles(self):
        result = run(self.handler('create t {}'))
        self.assertIn("0 role(s)", result)

    def test_assign_multiple_tasks(self):
        roles = json.dumps({"dev": "codes"})
        run(self.handler(f"create t {roles}"))
        run(self.handler("assign task one"))
        run(self.handler("assign task two"))
        result = run(self.handler("status"))
        self.assertIn("Pending tasks: 2", result)


if __name__ == "__main__":
    unittest.main()
