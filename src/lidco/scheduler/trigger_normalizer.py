"""TriggerEventNormalizer — normalize external event payloads to a common format."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NormalizedEvent:
    trigger_type: str
    source_id: str
    title: str
    body: str
    metadata: dict
    timestamp: str  # ISO format


class TriggerEventNormalizer:
    """Normalize various trigger payloads into a common NormalizedEvent."""

    def normalize(self, trigger_type: str, payload: dict) -> Optional[NormalizedEvent]:
        """Dispatch to type-specific parser. Return None on unknown type."""
        parsers = {
            "cron": self._parse_cron,
            "github_pr": self._parse_github_pr,
            "slack": self._parse_slack,
            "linear": self._parse_linear,
            "webhook": self._parse_webhook,
        }
        parser = parsers.get(trigger_type)
        if parser is None:
            return None
        return parser(payload)

    def render_template(self, template: str, event: NormalizedEvent) -> str:
        """Replace {{title}}, {{body}}, {{source_id}}, {{trigger_type}}, {{timestamp}}."""
        result = template
        replacements = {
            "title": event.title,
            "body": event.body,
            "source_id": event.source_id,
            "trigger_type": event.trigger_type,
            "timestamp": event.timestamp,
        }
        for key, value in replacements.items():
            result = result.replace("{{" + key + "}}", value)
        return result

    # ------------------------------------------------------------------ #
    # Type-specific parsers
    # ------------------------------------------------------------------ #

    def _parse_cron(self, payload: dict) -> NormalizedEvent:
        return NormalizedEvent(
            trigger_type="cron",
            source_id=payload.get("schedule", ""),
            title="Scheduled run",
            body="",
            metadata=dict(payload),
            timestamp=self._now_iso(),
        )

    def _parse_github_pr(self, payload: dict) -> NormalizedEvent:
        return NormalizedEvent(
            trigger_type="github_pr",
            source_id=str(payload.get("number", "")),
            title=payload.get("title", ""),
            body=payload.get("body", ""),
            metadata=dict(payload),
            timestamp=self._now_iso(),
        )

    def _parse_slack(self, payload: dict) -> NormalizedEvent:
        event = payload.get("event", {})
        return NormalizedEvent(
            trigger_type="slack",
            source_id=event.get("ts", ""),
            title=event.get("text", ""),
            body="",
            metadata=dict(payload),
            timestamp=self._now_iso(),
        )

    def _parse_linear(self, payload: dict) -> NormalizedEvent:
        issue = payload.get("issue", {})
        return NormalizedEvent(
            trigger_type="linear",
            source_id=issue.get("id", ""),
            title=issue.get("title", ""),
            body=issue.get("description", ""),
            metadata=dict(payload),
            timestamp=self._now_iso(),
        )

    def _parse_webhook(self, payload: dict) -> NormalizedEvent:
        return NormalizedEvent(
            trigger_type="webhook",
            source_id=payload.get("id", ""),
            title=payload.get("title", ""),
            body=json.dumps(payload),
            metadata=dict(payload),
            timestamp=self._now_iso(),
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
