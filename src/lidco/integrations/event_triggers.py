"""EventTriggerRouter — route external events (Sentry, Snyk, Slack, PagerDuty) to actions."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TriggerEvent:
    source: str       # "sentry" | "snyk" | "slack" | "pagerduty" | "custom"
    event_type: str   # "error" | "vulnerability" | "message" | "incident"
    title: str
    body: str
    metadata: dict
    received_at: float
    priority: str     # "critical" | "high" | "medium" | "low"


@dataclass
class TriggerAction:
    event: TriggerEvent
    action: str       # "start_session" | "start_flow" | "notify"
    instruction: str  # e.g. "Fix Sentry error: NullPointerException in auth.py"


class EventTriggerRouter:
    """Parse and route external webhook events to LIDCO actions."""

    # Built-in static parsers keyed by source name
    _BUILTIN_PARSERS: dict[str, Callable[[dict], "TriggerEvent"]] = {}

    def __init__(self) -> None:
        self._parsers: dict[str, Callable[[dict], TriggerEvent]] = {}
        self._rules: dict[tuple, str] = {}  # (source, event_type) -> action

    # ------------------------------------------------------------------
    # Source registration
    # ------------------------------------------------------------------

    def register_source(
        self, source: str, parser: Callable[[dict], TriggerEvent]
    ) -> None:
        """Register a custom parser for a named source."""
        self._parsers = {**self._parsers, source: parser}

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_event(self, source: str, raw_payload: dict) -> TriggerEvent | None:
        """Parse raw payload using registered or built-in parser."""
        # Try registered custom parser first
        if source in self._parsers:
            try:
                return self._parsers[source](raw_payload)
            except Exception:
                return None

        # Try built-in static parsers
        builtin_map: dict[str, Callable[[dict], TriggerEvent]] = {
            "sentry": EventTriggerRouter.parse_sentry,
            "snyk": EventTriggerRouter.parse_snyk,
            "slack": EventTriggerRouter.parse_slack,
            "pagerduty": EventTriggerRouter.parse_pagerduty,
        }
        if source in builtin_map:
            try:
                return builtin_map[source](raw_payload)
            except Exception:
                return None

        return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, event: TriggerEvent) -> TriggerAction:
        """Map event to an action based on rules or priority defaults."""
        key = (event.source, event.event_type)
        if key in self._rules:
            action = self._rules[key]
        else:
            # Default routing by priority
            if event.priority in ("critical", "high"):
                action = "start_session"
            elif event.priority == "medium":
                action = "start_flow"
            else:
                action = "notify"

        instruction = f"Fix {event.source} {event.event_type}: {event.title}"
        return TriggerAction(event=event, action=action, instruction=instruction)

    def add_rule(self, source: str, event_type: str, action: str) -> None:
        """Add or override a routing rule. Uses immutable dict replacement."""
        self._rules = {**self._rules, (source, event_type): action}

    # ------------------------------------------------------------------
    # Built-in static parsers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_sentry(payload: dict) -> TriggerEvent:
        """Parse a Sentry webhook payload."""
        event = payload.get("event", {})
        title = event.get("title") or payload.get("message") or "Unknown error"
        body = event.get("message") or payload.get("culprit") or ""
        level = event.get("level") or payload.get("level") or "error"
        level_lower = str(level).lower()
        if level_lower in ("fatal", "error"):
            priority = "critical"
        elif level_lower == "warning":
            priority = "high"
        else:
            priority = "low"

        return TriggerEvent(
            source="sentry",
            event_type="error",
            title=title,
            body=body,
            metadata=payload,
            received_at=time.time(),
            priority=priority,
        )

    @staticmethod
    def parse_snyk(payload: dict) -> TriggerEvent:
        """Parse a Snyk webhook payload."""
        title = payload.get("title") or payload.get("packageName") or "Unknown vulnerability"
        body = payload.get("description") or ""
        severity = str(payload.get("severity") or "medium").lower()
        priority_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        priority = priority_map.get(severity, "medium")

        return TriggerEvent(
            source="snyk",
            event_type="vulnerability",
            title=title,
            body=body,
            metadata=payload,
            received_at=time.time(),
            priority=priority,
        )

    @staticmethod
    def parse_slack(payload: dict) -> TriggerEvent:
        """Parse a Slack event webhook payload."""
        event = payload.get("event", {})
        title = payload.get("text") or event.get("text") or ""
        body = event.get("blocks") and str(event.get("blocks")) or ""

        return TriggerEvent(
            source="slack",
            event_type="message",
            title=title,
            body=body,
            metadata=payload,
            received_at=time.time(),
            priority="low",
        )

    @staticmethod
    def parse_pagerduty(payload: dict) -> TriggerEvent:
        """Parse a PagerDuty webhook payload."""
        messages = payload.get("messages", [])
        summary = ""
        urgency = "low"
        if messages:
            first = messages[0]
            pd_event = first.get("event", {})
            pd_payload = pd_event.get("payload", {})
            summary = pd_payload.get("summary") or ""
            urgency = str(pd_payload.get("severity") or first.get("urgency") or "low").lower()

        title = summary or payload.get("summary") or "PagerDuty incident"
        priority = "high" if urgency in ("critical", "high") else "medium" if urgency == "medium" else "low"

        return TriggerEvent(
            source="pagerduty",
            event_type="incident",
            title=title,
            body=summary,
            metadata=payload,
            received_at=time.time(),
            priority=priority,
        )
