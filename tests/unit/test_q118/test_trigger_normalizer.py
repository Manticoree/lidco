"""Tests for TriggerEventNormalizer (Task 723)."""
from __future__ import annotations

import json
import unittest

from lidco.scheduler.trigger_normalizer import NormalizedEvent, TriggerEventNormalizer


class TestTriggerEventNormalizer(unittest.TestCase):
    def setUp(self):
        self.norm = TriggerEventNormalizer()

    # -- cron ---------------------------------------------------------------

    def test_cron_basic(self):
        ev = self.norm.normalize("cron", {"schedule": "*/5 * * * *"})
        self.assertIsNotNone(ev)
        self.assertEqual(ev.trigger_type, "cron")
        self.assertEqual(ev.source_id, "*/5 * * * *")
        self.assertEqual(ev.title, "Scheduled run")
        self.assertEqual(ev.body, "")

    def test_cron_empty_payload(self):
        ev = self.norm.normalize("cron", {})
        self.assertEqual(ev.source_id, "")
        self.assertEqual(ev.title, "Scheduled run")

    def test_cron_has_timestamp(self):
        ev = self.norm.normalize("cron", {})
        self.assertIn("T", ev.timestamp)  # ISO format

    # -- github_pr ----------------------------------------------------------

    def test_github_pr_basic(self):
        payload = {"number": 42, "title": "Fix bug", "body": "Details here"}
        ev = self.norm.normalize("github_pr", payload)
        self.assertEqual(ev.trigger_type, "github_pr")
        self.assertEqual(ev.source_id, "42")
        self.assertEqual(ev.title, "Fix bug")
        self.assertEqual(ev.body, "Details here")

    def test_github_pr_missing_fields(self):
        ev = self.norm.normalize("github_pr", {})
        self.assertEqual(ev.source_id, "")
        self.assertEqual(ev.title, "")

    def test_github_pr_number_string(self):
        ev = self.norm.normalize("github_pr", {"number": "99"})
        self.assertEqual(ev.source_id, "99")

    # -- slack --------------------------------------------------------------

    def test_slack_basic(self):
        payload = {"event": {"ts": "123.456", "text": "Hello"}}
        ev = self.norm.normalize("slack", payload)
        self.assertEqual(ev.trigger_type, "slack")
        self.assertEqual(ev.source_id, "123.456")
        self.assertEqual(ev.title, "Hello")
        self.assertEqual(ev.body, "")

    def test_slack_empty_event(self):
        ev = self.norm.normalize("slack", {})
        self.assertEqual(ev.source_id, "")
        self.assertEqual(ev.title, "")

    def test_slack_nested_event(self):
        payload = {"event": {"ts": "1", "text": "msg"}, "team": "T1"}
        ev = self.norm.normalize("slack", payload)
        self.assertEqual(ev.metadata["team"], "T1")

    # -- linear -------------------------------------------------------------

    def test_linear_basic(self):
        payload = {"issue": {"id": "LIN-123", "title": "Add feature", "description": "Desc"}}
        ev = self.norm.normalize("linear", payload)
        self.assertEqual(ev.trigger_type, "linear")
        self.assertEqual(ev.source_id, "LIN-123")
        self.assertEqual(ev.title, "Add feature")
        self.assertEqual(ev.body, "Desc")

    def test_linear_missing_issue(self):
        ev = self.norm.normalize("linear", {})
        self.assertEqual(ev.source_id, "")
        self.assertEqual(ev.title, "")
        self.assertEqual(ev.body, "")

    def test_linear_partial_issue(self):
        ev = self.norm.normalize("linear", {"issue": {"id": "X"}})
        self.assertEqual(ev.source_id, "X")
        self.assertEqual(ev.title, "")

    # -- webhook ------------------------------------------------------------

    def test_webhook_basic(self):
        payload = {"id": "w1", "title": "Hook fired", "extra": "data"}
        ev = self.norm.normalize("webhook", payload)
        self.assertEqual(ev.trigger_type, "webhook")
        self.assertEqual(ev.source_id, "w1")
        self.assertEqual(ev.title, "Hook fired")
        self.assertIn("extra", ev.body)  # body is json.dumps(payload)

    def test_webhook_body_is_json(self):
        payload = {"id": "w1", "title": "T"}
        ev = self.norm.normalize("webhook", payload)
        parsed = json.loads(ev.body)
        self.assertEqual(parsed["id"], "w1")

    def test_webhook_empty(self):
        ev = self.norm.normalize("webhook", {})
        self.assertEqual(ev.source_id, "")
        self.assertEqual(ev.title, "")

    # -- unknown type -------------------------------------------------------

    def test_unknown_type_returns_none(self):
        self.assertIsNone(self.norm.normalize("jira", {}))

    def test_unknown_type_no_exception(self):
        result = self.norm.normalize("unknown_system", {"data": 1})
        self.assertIsNone(result)

    # -- render_template ----------------------------------------------------

    def test_render_title(self):
        ev = NormalizedEvent("cron", "s1", "My Title", "body", {}, "2024-01-01T00:00:00")
        out = self.norm.render_template("Fix: {{title}}", ev)
        self.assertEqual(out, "Fix: My Title")

    def test_render_body(self):
        ev = NormalizedEvent("cron", "s1", "T", "Details", {}, "2024-01-01T00:00:00")
        out = self.norm.render_template("{{body}}", ev)
        self.assertEqual(out, "Details")

    def test_render_source_id(self):
        ev = NormalizedEvent("github_pr", "42", "T", "", {}, "2024-01-01T00:00:00")
        out = self.norm.render_template("PR #{{source_id}}", ev)
        self.assertEqual(out, "PR #42")

    def test_render_trigger_type(self):
        ev = NormalizedEvent("slack", "ts", "T", "", {}, "2024-01-01T00:00:00")
        out = self.norm.render_template("Type: {{trigger_type}}", ev)
        self.assertEqual(out, "Type: slack")

    def test_render_timestamp(self):
        ev = NormalizedEvent("cron", "", "T", "", {}, "2024-01-01T00:00:00")
        out = self.norm.render_template("At {{timestamp}}", ev)
        self.assertEqual(out, "At 2024-01-01T00:00:00")

    def test_render_multiple_vars(self):
        ev = NormalizedEvent("cron", "s1", "T1", "B1", {}, "ts")
        out = self.norm.render_template("{{title}} - {{body}} ({{source_id}})", ev)
        self.assertEqual(out, "T1 - B1 (s1)")

    def test_render_no_vars(self):
        ev = NormalizedEvent("cron", "", "", "", {}, "")
        out = self.norm.render_template("No vars here", ev)
        self.assertEqual(out, "No vars here")

    def test_render_unknown_var_unchanged(self):
        ev = NormalizedEvent("cron", "", "", "", {}, "")
        out = self.norm.render_template("{{unknown}}", ev)
        self.assertEqual(out, "{{unknown}}")

    # -- metadata preserved -------------------------------------------------

    def test_metadata_preserved(self):
        payload = {"schedule": "*/5", "extra": "val"}
        ev = self.norm.normalize("cron", payload)
        self.assertEqual(ev.metadata["extra"], "val")


if __name__ == "__main__":
    unittest.main()
