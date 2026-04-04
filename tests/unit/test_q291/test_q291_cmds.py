"""Tests for lidco.cli.commands.q291_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q291_cmds import register_q291_commands, _state


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ291Commands(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = _FakeRegistry()
        register_q291_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("jira", names)
        self.assertIn("jira-sync", names)
        self.assertIn("jira-sprint", names)
        self.assertIn("jira-report", names)

    # -- /jira --
    def test_jira_projects(self):
        handler = self.registry.commands["jira"].handler
        result = asyncio.run(handler("projects"))
        self.assertIn("project", result.lower())

    def test_jira_create(self):
        handler = self.registry.commands["jira"].handler
        result = asyncio.run(handler("create Fix login"))
        self.assertIn("Created", result)
        self.assertIn("Fix login", result)

    def test_jira_create_empty(self):
        handler = self.registry.commands["jira"].handler
        result = asyncio.run(handler("create"))
        self.assertIn("Usage", result)

    def test_jira_get(self):
        handler = self.registry.commands["jira"].handler
        asyncio.run(handler("create Test issue"))
        result = asyncio.run(handler("get PROJ-1"))
        self.assertIn("Test issue", result)

    def test_jira_get_not_found(self):
        handler = self.registry.commands["jira"].handler
        result = asyncio.run(handler("get NOPE-1"))
        self.assertIn("not found", result)

    def test_jira_search(self):
        handler = self.registry.commands["jira"].handler
        asyncio.run(handler("create Alpha task"))
        result = asyncio.run(handler("search project = PROJ"))
        self.assertIn("Alpha task", result)

    def test_jira_delete(self):
        handler = self.registry.commands["jira"].handler
        asyncio.run(handler("create Gone"))
        result = asyncio.run(handler("delete PROJ-1"))
        self.assertIn("Deleted", result)

    def test_jira_unknown_subcmd(self):
        handler = self.registry.commands["jira"].handler
        result = asyncio.run(handler("wat"))
        self.assertIn("Usage", result)

    # -- /jira-sync --
    def test_sync_push(self):
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("push My TODO"))
        self.assertIn("Synced", result)

    def test_sync_pull(self):
        jira_handler = self.registry.commands["jira"].handler
        asyncio.run(jira_handler("create Pullable"))
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("pull"))
        self.assertIn("Pulled", result)

    def test_sync_status(self):
        jira_handler = self.registry.commands["jira"].handler
        asyncio.run(jira_handler("create WIP"))
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("status PROJ-1 Done"))
        self.assertIn("Updated", result)

    def test_sync_link_pr(self):
        jira_handler = self.registry.commands["jira"].handler
        asyncio.run(jira_handler("create Linked"))
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("link-pr PROJ-1 https://github.com/a/pull/1"))
        self.assertIn("Linked PR", result)

    def test_sync_pending(self):
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("pending"))
        self.assertIn("No pending", result)

    def test_sync_unknown(self):
        handler = self.registry.commands["jira-sync"].handler
        result = asyncio.run(handler("wat"))
        self.assertIn("Usage", result)

    # -- /jira-sprint --
    def test_sprint_create(self):
        handler = self.registry.commands["jira-sprint"].handler
        result = asyncio.run(handler("create Sprint Alpha"))
        self.assertIn("Created sprint", result)

    def test_sprint_start(self):
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        result = asyncio.run(handler("start sprint-1"))
        self.assertIn("Started", result)

    def test_sprint_close(self):
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        asyncio.run(handler("start sprint-1"))
        result = asyncio.run(handler("close sprint-1"))
        self.assertIn("Closed", result)

    def test_sprint_add_issue(self):
        jira_handler = self.registry.commands["jira"].handler
        asyncio.run(jira_handler("create Task A"))
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        result = asyncio.run(handler("add sprint-1 PROJ-1"))
        self.assertIn("Added", result)

    def test_sprint_estimate(self):
        jira_handler = self.registry.commands["jira"].handler
        asyncio.run(jira_handler("create Task A"))
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        asyncio.run(handler("add sprint-1 PROJ-1"))
        result = asyncio.run(handler("estimate PROJ-1 5"))
        self.assertIn("Estimated", result)

    def test_sprint_capacity(self):
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        result = asyncio.run(handler("capacity sprint-1"))
        self.assertIn("Capacity", result)

    def test_sprint_list(self):
        handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(handler("create S1"))
        result = asyncio.run(handler("list"))
        self.assertIn("sprint", result.lower())

    def test_sprint_unknown(self):
        handler = self.registry.commands["jira-sprint"].handler
        result = asyncio.run(handler("wat"))
        self.assertIn("Usage", result)

    # -- /jira-report --
    def test_report_summary(self):
        handler = self.registry.commands["jira-report"].handler
        result = asyncio.run(handler("summary"))
        self.assertIn("Summary", result)

    def test_report_velocity_empty(self):
        handler = self.registry.commands["jira-report"].handler
        result = asyncio.run(handler("velocity"))
        self.assertIn("No closed", result)

    def test_report_burndown(self):
        sprint_handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(sprint_handler("create S1"))
        handler = self.registry.commands["jira-report"].handler
        result = asyncio.run(handler("burndown sprint-1"))
        self.assertIn("Burndown", result)

    def test_report_prediction(self):
        sprint_handler = self.registry.commands["jira-sprint"].handler
        asyncio.run(sprint_handler("create S1"))
        handler = self.registry.commands["jira-report"].handler
        result = asyncio.run(handler("prediction sprint-1"))
        self.assertIn("Prediction", result)

    def test_report_unknown(self):
        handler = self.registry.commands["jira-report"].handler
        result = asyncio.run(handler("wat"))
        self.assertIn("Usage", result)
