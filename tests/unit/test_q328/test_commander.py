"""Tests for lidco.sre.commander — Incident Commander."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.sre.commander import (
    CommunicationTemplate,
    Incident,
    IncidentCommander,
    IncidentError,
    IncidentStatus,
    PostmortemReport,
    Severity,
    StatusPageEntry,
    StatusUpdate,
)


class TestIncidentDataclasses(unittest.TestCase):
    def test_incident_defaults(self) -> None:
        inc = Incident(title="db down", severity=Severity.SEV1)
        self.assertEqual(inc.status, IncidentStatus.DECLARED)
        self.assertTrue(inc.is_active())
        self.assertIsNone(inc.resolved_at)

    def test_incident_duration(self) -> None:
        now = time.time()
        inc = Incident(title="x", created_at=now - 300, resolved_at=now)
        self.assertAlmostEqual(inc.duration_seconds(), 300, delta=1)

    def test_incident_is_active(self) -> None:
        inc = Incident(status=IncidentStatus.RESOLVED)
        self.assertFalse(inc.is_active())
        inc2 = Incident(status=IncidentStatus.POSTMORTEM)
        self.assertFalse(inc2.is_active())
        inc3 = Incident(status=IncidentStatus.INVESTIGATING)
        self.assertTrue(inc3.is_active())

    def test_status_update(self) -> None:
        su = StatusUpdate(message="investigating", status=IncidentStatus.INVESTIGATING, author="alice")
        self.assertEqual(su.author, "alice")

    def test_communication_template_render(self) -> None:
        tpl = CommunicationTemplate(name="alert", template="{{service}} is down — severity {{level}}")
        rendered = tpl.render(service="API", level="SEV1")
        self.assertEqual(rendered, "API is down — severity SEV1")

    def test_communication_template_render_no_vars(self) -> None:
        tpl = CommunicationTemplate(name="simple", template="All clear.")
        self.assertEqual(tpl.render(), "All clear.")

    def test_status_page_entry(self) -> None:
        entry = StatusPageEntry(
            incident_id="abc", title="outage",
            severity=Severity.SEV1, status=IncidentStatus.INVESTIGATING,
            message="Looking into it",
        )
        self.assertEqual(entry.title, "outage")

    def test_postmortem_summary(self) -> None:
        pm = PostmortemReport(
            incident_id="x", title="DB outage", severity=Severity.SEV1,
            duration_seconds=1800, timeline=[],
            root_cause="OOM", impact="100% of users", action_items=["add alerting"],
        )
        summary = pm.summary()
        self.assertIn("DB outage", summary)
        self.assertIn("sev1", summary)
        self.assertIn("OOM", summary)
        self.assertIn("1", summary)  # action item count

    def test_severity_values(self) -> None:
        self.assertEqual(Severity.SEV1.value, "sev1")
        self.assertEqual(Severity.SEV4.value, "sev4")


class TestIncidentCommander(unittest.TestCase):
    def setUp(self) -> None:
        self.cmdr = IncidentCommander()

    def test_declare(self) -> None:
        inc = self.cmdr.declare("API down", Severity.SEV1, commander="alice")
        self.assertEqual(inc.title, "API down")
        self.assertEqual(inc.severity, Severity.SEV1)
        self.assertEqual(inc.commander, "alice")
        self.assertEqual(inc.status, IncidentStatus.DECLARED)
        self.assertEqual(len(inc.updates), 1)

    def test_declare_no_title_raises(self) -> None:
        with self.assertRaises(IncidentError):
            self.cmdr.declare("", Severity.SEV2)

    def test_get(self) -> None:
        inc = self.cmdr.declare("x", Severity.SEV3)
        result = self.cmdr.get(inc.id)
        self.assertEqual(result.title, "x")

    def test_get_not_found(self) -> None:
        with self.assertRaises(IncidentError):
            self.cmdr.get("nope")

    def test_list_incidents(self) -> None:
        self.cmdr.declare("a", Severity.SEV1)
        self.cmdr.declare("b", Severity.SEV2)
        self.assertEqual(len(self.cmdr.list_incidents()), 2)

    def test_list_incidents_active_only(self) -> None:
        inc = self.cmdr.declare("a", Severity.SEV1)
        self.cmdr.update_status(inc.id, IncidentStatus.RESOLVED, "fixed")
        self.cmdr.declare("b", Severity.SEV2)
        active = self.cmdr.list_incidents(active_only=True)
        self.assertEqual(len(active), 1)

    def test_update_status(self) -> None:
        inc = self.cmdr.declare("x", Severity.SEV2)
        updated = self.cmdr.update_status(inc.id, IncidentStatus.INVESTIGATING, "looking")
        self.assertEqual(updated.status, IncidentStatus.INVESTIGATING)
        self.assertEqual(len(updated.updates), 2)

    def test_update_status_resolved_sets_time(self) -> None:
        inc = self.cmdr.declare("x", Severity.SEV3)
        self.cmdr.update_status(inc.id, IncidentStatus.RESOLVED, "done")
        self.assertIsNotNone(inc.resolved_at)

    def test_add_template(self) -> None:
        tpl = self.cmdr.add_template(CommunicationTemplate(name="alert", template="Alert: {{msg}}"))
        self.assertEqual(len(self.cmdr.list_templates()), 1)
        self.assertEqual(tpl.name, "alert")

    def test_add_template_no_name_raises(self) -> None:
        with self.assertRaises(IncidentError):
            self.cmdr.add_template(CommunicationTemplate(name=""))

    def test_get_template_not_found(self) -> None:
        with self.assertRaises(IncidentError):
            self.cmdr.get_template("bad")

    def test_render_template(self) -> None:
        tpl = self.cmdr.add_template(CommunicationTemplate(name="t", template="Hello {{name}}"))
        result = self.cmdr.render_template(tpl.id, name="World")
        self.assertEqual(result, "Hello World")

    def test_publish_status(self) -> None:
        inc = self.cmdr.declare("outage", Severity.SEV1)
        entry = self.cmdr.publish_status(inc.id, "Investigating the issue")
        self.assertEqual(entry.incident_id, inc.id)
        self.assertEqual(len(self.cmdr.status_page()), 1)

    def test_publish_status_not_found(self) -> None:
        with self.assertRaises(IncidentError):
            self.cmdr.publish_status("nope", "msg")

    def test_generate_postmortem(self) -> None:
        inc = self.cmdr.declare("bug", Severity.SEV2)
        self.cmdr.update_status(inc.id, IncidentStatus.RESOLVED, "fixed")
        pm = self.cmdr.generate_postmortem(inc.id, root_cause="OOM", action_items=["add memory"])
        self.assertEqual(pm.root_cause, "OOM")
        self.assertEqual(len(pm.action_items), 1)

    def test_generate_postmortem_active_raises(self) -> None:
        inc = self.cmdr.declare("active", Severity.SEV1)
        with self.assertRaises(IncidentError):
            self.cmdr.generate_postmortem(inc.id)


if __name__ == "__main__":
    unittest.main()
