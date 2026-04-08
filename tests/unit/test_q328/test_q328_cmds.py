"""Tests for lidco.cli.commands.q328_cmds — /slo, /incident, /runbook, /oncall."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _make_registry() -> MagicMock:
    """Create a mock registry and register Q328 commands onto it."""
    from lidco.cli.commands.q328_cmds import register_q328_commands

    registry = MagicMock()
    handlers: dict[str, object] = {}

    def capture(name: str, desc: str, handler: object) -> None:
        handlers[name] = handler

    registry.register_async.side_effect = capture
    register_q328_commands(registry)
    registry._handlers = handlers
    return registry


class TestSLOCommand(unittest.TestCase):
    def setUp(self) -> None:
        reg = _make_registry()
        self.handler = reg._handlers["slo"]

    def test_no_args_shows_usage(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_define(self) -> None:
        result = asyncio.run(self.handler("define api-avail 0.999"))
        self.assertIn("Defined SLO", result)
        self.assertIn("api-avail", result)

    def test_define_missing_args(self) -> None:
        result = asyncio.run(self.handler("define"))
        self.assertIn("Usage", result)

    def test_define_bad_target(self) -> None:
        result = asyncio.run(self.handler("define x not-a-number"))
        self.assertIn("Invalid target", result)

    def test_list_empty(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("No SLOs", result)

    def test_status(self) -> None:
        result = asyncio.run(self.handler("status abc"))
        self.assertIn("abc", result)

    def test_status_missing_id(self) -> None:
        result = asyncio.run(self.handler("status"))
        self.assertIn("Usage", result)

    def test_record_good(self) -> None:
        result = asyncio.run(self.handler("record latency good"))
        self.assertIn("good", result)
        self.assertIn("latency", result)

    def test_record_bad(self) -> None:
        result = asyncio.run(self.handler("record latency bad"))
        self.assertIn("bad", result)

    def test_record_missing_args(self) -> None:
        result = asyncio.run(self.handler("record"))
        self.assertIn("Usage", result)

    def test_report_empty(self) -> None:
        result = asyncio.run(self.handler("report"))
        self.assertIn("No SLOs", result)

    def test_alert(self) -> None:
        result = asyncio.run(self.handler("alert slo-123 2.0"))
        self.assertIn("slo-123", result)

    def test_unknown_subcommand(self) -> None:
        result = asyncio.run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


class TestIncidentCommand(unittest.TestCase):
    def setUp(self) -> None:
        reg = _make_registry()
        self.handler = reg._handlers["incident"]

    def test_no_args_shows_usage(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_declare(self) -> None:
        result = asyncio.run(self.handler("declare db-outage sev1"))
        self.assertIn("Incident declared", result)
        self.assertIn("db-outage", result)

    def test_declare_missing_args(self) -> None:
        result = asyncio.run(self.handler("declare"))
        self.assertIn("Usage", result)

    def test_declare_bad_severity(self) -> None:
        result = asyncio.run(self.handler("declare x critical"))
        self.assertIn("Invalid severity", result)

    def test_list_empty(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("No incidents", result)

    def test_update(self) -> None:
        result = asyncio.run(self.handler("update id123 investigating looking"))
        self.assertIn("Updated", result)

    def test_update_missing_args(self) -> None:
        result = asyncio.run(self.handler("update"))
        self.assertIn("Usage", result)

    def test_postmortem(self) -> None:
        result = asyncio.run(self.handler("postmortem id123"))
        self.assertIn("id123", result)

    def test_postmortem_missing_args(self) -> None:
        result = asyncio.run(self.handler("postmortem"))
        self.assertIn("Usage", result)

    def test_status_page_empty(self) -> None:
        result = asyncio.run(self.handler("status-page"))
        self.assertIn("empty", result)

    def test_unknown_subcommand(self) -> None:
        result = asyncio.run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


class TestRunbookCommand(unittest.TestCase):
    def setUp(self) -> None:
        reg = _make_registry()
        self.handler = reg._handlers["runbook"]

    def test_no_args_shows_usage(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_create(self) -> None:
        result = asyncio.run(self.handler("create deploy-prod"))
        self.assertIn("Created runbook", result)
        self.assertIn("deploy-prod", result)

    def test_create_missing_args(self) -> None:
        result = asyncio.run(self.handler("create"))
        self.assertIn("Usage", result)

    def test_list_empty(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("No runbooks", result)

    def test_show(self) -> None:
        result = asyncio.run(self.handler("show rb-id"))
        self.assertIn("rb-id", result)

    def test_show_missing_args(self) -> None:
        result = asyncio.run(self.handler("show"))
        self.assertIn("Usage", result)

    def test_from_procedure(self) -> None:
        result = asyncio.run(self.handler("from-procedure deploy step1; step2; step3"))
        self.assertIn("Generated runbook", result)
        self.assertIn("deploy", result)

    def test_from_procedure_missing_args(self) -> None:
        result = asyncio.run(self.handler("from-procedure"))
        self.assertIn("Usage", result)

    def test_version(self) -> None:
        result = asyncio.run(self.handler("version rb-id 2.0.0"))
        self.assertIn("2.0.0", result)

    def test_version_missing_args(self) -> None:
        result = asyncio.run(self.handler("version"))
        self.assertIn("Usage", result)

    def test_checks(self) -> None:
        result = asyncio.run(self.handler("checks rb-id"))
        self.assertIn("rb-id", result)

    def test_checks_missing_args(self) -> None:
        result = asyncio.run(self.handler("checks"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self) -> None:
        result = asyncio.run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


class TestOnCallCommand(unittest.TestCase):
    def setUp(self) -> None:
        reg = _make_registry()
        self.handler = reg._handlers["oncall"]

    def test_no_args_shows_usage(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_add_person(self) -> None:
        result = asyncio.run(self.handler("add-person Alice alice@test.com"))
        self.assertIn("Added", result)
        self.assertIn("Alice", result)

    def test_add_person_missing_args(self) -> None:
        result = asyncio.run(self.handler("add-person"))
        self.assertIn("Usage", result)

    def test_list_empty(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("No on-call", result)

    def test_who_none(self) -> None:
        result = asyncio.run(self.handler("who"))
        self.assertIn("No one", result)

    def test_override(self) -> None:
        result = asyncio.run(self.handler("override id1 id2 8"))
        self.assertIn("Override", result)

    def test_override_missing_args(self) -> None:
        result = asyncio.run(self.handler("override"))
        self.assertIn("Usage", result)

    def test_fatigue(self) -> None:
        result = asyncio.run(self.handler("fatigue person-1"))
        self.assertIn("person-1", result)

    def test_fatigue_missing_args(self) -> None:
        result = asyncio.run(self.handler("fatigue"))
        self.assertIn("Usage", result)

    def test_handoff(self) -> None:
        result = asyncio.run(self.handler("handoff id1 id2 notes-here"))
        self.assertIn("Handoff", result)

    def test_handoff_missing_args(self) -> None:
        result = asyncio.run(self.handler("handoff"))
        self.assertIn("Usage", result)

    def test_policy(self) -> None:
        result = asyncio.run(self.handler("policy default-esc"))
        self.assertIn("Created escalation policy", result)
        self.assertIn("default-esc", result)

    def test_policy_missing_args(self) -> None:
        result = asyncio.run(self.handler("policy"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self) -> None:
        result = asyncio.run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
