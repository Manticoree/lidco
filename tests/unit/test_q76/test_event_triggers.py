"""Tests for EventTriggerRouter — T505."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.integrations.event_triggers import (
    EventTriggerRouter,
    TriggerAction,
    TriggerEvent,
)


class TestParseSentry:
    def test_extracts_title(self):
        payload = {"event": {"title": "NullPointerException in auth.py", "level": "error"}}
        event = EventTriggerRouter.parse_sentry(payload)
        assert event.title == "NullPointerException in auth.py"
        assert event.source == "sentry"
        assert event.event_type == "error"

    def test_priority_critical_for_error(self):
        payload = {"event": {"title": "Error", "level": "error"}}
        event = EventTriggerRouter.parse_sentry(payload)
        assert event.priority == "critical"

    def test_priority_high_for_warning(self):
        payload = {"event": {"title": "Warn", "level": "warning"}}
        event = EventTriggerRouter.parse_sentry(payload)
        assert event.priority == "high"

    def test_priority_low_for_info(self):
        payload = {"event": {"title": "Info", "level": "info"}}
        event = EventTriggerRouter.parse_sentry(payload)
        assert event.priority == "low"


class TestParseSnyk:
    def test_extracts_vulnerability_info(self):
        payload = {"title": "SQL Injection", "packageName": "requests", "severity": "high"}
        event = EventTriggerRouter.parse_snyk(payload)
        assert event.title == "SQL Injection"
        assert event.event_type == "vulnerability"
        assert event.priority == "high"

    def test_uses_package_name_as_fallback(self):
        payload = {"packageName": "lodash", "severity": "critical"}
        event = EventTriggerRouter.parse_snyk(payload)
        assert event.title == "lodash"
        assert event.priority == "critical"


class TestParseSlack:
    def test_extracts_message_text(self):
        payload = {"text": "Hello from Slack", "event": {}}
        event = EventTriggerRouter.parse_slack(payload)
        assert event.title == "Hello from Slack"
        assert event.event_type == "message"
        assert event.priority == "low"

    def test_extracts_from_event_sub_key(self):
        payload = {"event": {"text": "Event text"}}
        event = EventTriggerRouter.parse_slack(payload)
        assert event.title == "Event text"


class TestParsePagerDuty:
    def test_extracts_incident_info(self):
        payload = {
            "messages": [
                {
                    "event": {
                        "payload": {
                            "summary": "Database is down",
                            "severity": "critical",
                        }
                    }
                }
            ]
        }
        event = EventTriggerRouter.parse_pagerduty(payload)
        assert event.title == "Database is down"
        assert event.event_type == "incident"
        assert event.priority == "high"


class TestRegisterSource:
    def test_custom_parser_called(self):
        router = EventTriggerRouter()
        mock_parser = MagicMock(return_value=TriggerEvent(
            source="custom", event_type="error", title="Custom",
            body="", metadata={}, received_at=0.0, priority="high",
        ))
        router.register_source("custom", mock_parser)
        event = router.parse_event("custom", {"key": "value"})
        mock_parser.assert_called_once_with({"key": "value"})
        assert event is not None
        assert event.source == "custom"

    def test_parse_event_uses_custom_parser(self):
        router = EventTriggerRouter()

        def my_parser(p: dict) -> TriggerEvent:
            return TriggerEvent(
                source="mine", event_type="alert", title=p["msg"],
                body="", metadata=p, received_at=0.0, priority="medium",
            )

        router.register_source("mine", my_parser)
        event = router.parse_event("mine", {"msg": "hello"})
        assert event.title == "hello"

    def test_parse_event_unknown_source_returns_none(self):
        router = EventTriggerRouter()
        result = router.parse_event("unknown_source", {})
        assert result is None


class TestRoute:
    def test_route_critical_to_start_session(self):
        router = EventTriggerRouter()
        event = TriggerEvent(
            source="sentry", event_type="error", title="Crash",
            body="", metadata={}, received_at=0.0, priority="critical",
        )
        action = router.route(event)
        assert action.action == "start_session"

    def test_route_low_to_notify(self):
        router = EventTriggerRouter()
        event = TriggerEvent(
            source="slack", event_type="message", title="FYI",
            body="", metadata={}, received_at=0.0, priority="low",
        )
        action = router.route(event)
        assert action.action == "notify"

    def test_route_medium_to_start_flow(self):
        router = EventTriggerRouter()
        event = TriggerEvent(
            source="snyk", event_type="vulnerability", title="Low vuln",
            body="", metadata={}, received_at=0.0, priority="medium",
        )
        action = router.route(event)
        assert action.action == "start_flow"

    def test_add_rule_overrides_default(self):
        router = EventTriggerRouter()
        router.add_rule("slack", "message", "start_session")
        event = TriggerEvent(
            source="slack", event_type="message", title="Alert!",
            body="", metadata={}, received_at=0.0, priority="low",
        )
        action = router.route(event)
        assert action.action == "start_session"

    def test_instruction_format(self):
        router = EventTriggerRouter()
        event = TriggerEvent(
            source="sentry", event_type="error", title="NullPtr",
            body="", metadata={}, received_at=0.0, priority="critical",
        )
        action = router.route(event)
        assert "sentry" in action.instruction
        assert "NullPtr" in action.instruction
