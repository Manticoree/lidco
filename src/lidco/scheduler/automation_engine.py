"""AutomationEngine — event-driven YAML automation rules (Cursor Automations parity)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
    _yaml = None  # type: ignore[assignment]


@dataclass
class AutomationRule:
    name: str
    trigger_type: str  # "cron" | "github_issue" | "github_pr" | "webhook"
    trigger_config: dict
    task_template: str
    output_type: str  # "pr" | "comment" | "message" | "log"
    enabled: bool = True


@dataclass
class AutomationResult:
    rule_name: str
    triggered_at: float
    task: str
    output: str
    success: bool
    error: str = ""


def _render_template(template: str, event: dict) -> str:
    """Replace {event.key} placeholders with values from event dict."""

    def _replace(m: re.Match) -> str:
        key = m.group(1)  # e.g. "event.title"
        parts = key.split(".", 1)
        if parts[0] == "event" and len(parts) == 2:
            return str(event.get(parts[1], f"{{{key}}}"))
        return m.group(0)

    return re.sub(r"\{([\w.]+)\}", _replace, template)


class AutomationEngine:
    """Load YAML automation rules and run them against events."""

    def __init__(
        self,
        rules_path: str | Path | None = None,
        agent_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._rules_path = Path(rules_path) if rules_path else Path(".lidco/automations.yaml")
        self._agent_fn = agent_fn
        self._rules: list[AutomationRule] = []

    # ------------------------------------------------------------------
    # Rules management
    # ------------------------------------------------------------------

    def load_rules(self) -> list[AutomationRule]:
        """Load rules from YAML file. Returns loaded rules (may be [])."""
        if not self._rules_path.exists():
            self._rules = []
            return []

        raw = self._rules_path.read_text(encoding="utf-8")
        try:
            if _HAS_YAML:
                data = _yaml.safe_load(raw) or {}
            else:
                import json
                data = json.loads(raw)
        except Exception:
            self._rules = []
            return []

        rules = []
        for entry in data.get("rules", []):
            try:
                rules.append(AutomationRule(
                    name=entry["name"],
                    trigger_type=entry.get("trigger_type", "webhook"),
                    trigger_config=entry.get("trigger_config", {}),
                    task_template=entry.get("task_template", ""),
                    output_type=entry.get("output_type", "log"),
                    enabled=entry.get("enabled", True),
                ))
            except (KeyError, TypeError):
                continue

        self._rules = rules
        return list(self._rules)

    @property
    def rules(self) -> list[AutomationRule]:
        return list(self._rules)

    def add_rule(self, rule: AutomationRule) -> None:
        self._rules = [*self._rules, rule]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, event: dict) -> list[AutomationRule]:
        """Return rules that match the given event (enabled + matching trigger_type)."""
        event_type = event.get("type", "")
        matching = []
        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule.trigger_type == event_type or rule.trigger_type == "webhook":
                matching.append(rule)
        return matching

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_rule(self, rule: AutomationRule, event: dict) -> AutomationResult:
        """Render task template and call agent_fn."""
        task = _render_template(rule.task_template, event)
        ts = time.time()
        if self._agent_fn is None:
            return AutomationResult(
                rule_name=rule.name,
                triggered_at=ts,
                task=task,
                output="[no agent configured]",
                success=True,
            )
        try:
            output = self._agent_fn(task)
            return AutomationResult(
                rule_name=rule.name,
                triggered_at=ts,
                task=task,
                output=output,
                success=True,
            )
        except Exception as exc:
            return AutomationResult(
                rule_name=rule.name,
                triggered_at=ts,
                task=task,
                output="",
                success=False,
                error=str(exc),
            )

    def tick(self) -> list[AutomationResult]:
        """Run all enabled cron rules (simplified: runs all cron rules)."""
        results = []
        for rule in self._rules:
            if rule.enabled and rule.trigger_type == "cron":
                result = self.run_rule(rule, {"type": "cron"})
                results.append(result)
        return results
