"""Tests for AuditTrail — Task 322."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lidco.security.audit_trail import AuditEvent, AuditTrail


@pytest.fixture
def trail(tmp_path):
    t = AuditTrail(db_path=tmp_path / "audit.db", session_id="test-session")
    yield t
    t.close()


# ---------------------------------------------------------------------------
# record()
# ---------------------------------------------------------------------------

class TestAuditTrailRecord:
    def test_record_returns_event_id(self, trail):
        eid = trail.record("tool_call", "coder", "bash", reasoning="running tests")
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_record_stores_event(self, trail):
        eid = trail.record("tool_call", "coder", "bash", details={"command": "ls"})
        event = trail.get(eid)
        assert event is not None
        assert event.action == "bash"
        assert event.details == {"command": "ls"}

    def test_record_increments_count(self, trail):
        assert trail.count() == 0
        trail.record("tool_call", "coder", "bash")
        trail.record("tool_call", "tester", "run_tests")
        assert trail.count() == 2

    def test_custom_event_id(self, trail):
        eid = trail.record("llm_call", "coder", "complete", event_id="my-event-id")
        assert eid == "my-event-id"
        event = trail.get("my-event-id")
        assert event is not None


# ---------------------------------------------------------------------------
# update_outcome()
# ---------------------------------------------------------------------------

class TestAuditTrailUpdateOutcome:
    def test_update_outcome(self, trail):
        eid = trail.record("tool_call", "coder", "bash", outcome="pending")
        trail.update_outcome(eid, outcome="success", duration_ms=150.0)
        event = trail.get(eid)
        assert event.outcome == "success"
        assert event.duration_ms == 150.0


# ---------------------------------------------------------------------------
# query()
# ---------------------------------------------------------------------------

class TestAuditTrailQuery:
    def test_query_all(self, trail):
        trail.record("tool_call", "coder", "bash")
        trail.record("llm_call", "reviewer", "complete")
        events = trail.query()
        assert len(events) == 2

    def test_query_by_agent(self, trail):
        trail.record("tool_call", "coder", "bash")
        trail.record("tool_call", "tester", "run_tests")
        events = trail.query(agent="coder")
        assert len(events) == 1
        assert events[0].agent == "coder"

    def test_query_by_event_type(self, trail):
        trail.record("tool_call", "coder", "bash")
        trail.record("llm_call", "coder", "complete")
        events = trail.query(event_type="llm_call")
        assert len(events) == 1

    def test_query_by_session(self, tmp_path):
        t1 = AuditTrail(db_path=tmp_path / "a.db", session_id="session-A")
        t2 = AuditTrail(db_path=tmp_path / "a.db", session_id="session-B")
        t1.record("tool_call", "coder", "bash")
        t2.record("tool_call", "coder", "bash")
        events_a = t1.query(session_id="session-A")
        assert len(events_a) == 1
        t1.close()
        t2.close()

    def test_query_since(self, trail):
        trail.record("tool_call", "coder", "bash")
        future = time.time() + 1000
        events = trail.query(since=future)
        assert len(events) == 0

    def test_query_limit(self, trail):
        for _ in range(10):
            trail.record("tool_call", "coder", "bash")
        events = trail.query(limit=5)
        assert len(events) == 5


# ---------------------------------------------------------------------------
# export_json()
# ---------------------------------------------------------------------------

class TestAuditTrailExport:
    def test_export_json_string(self, trail):
        trail.record("tool_call", "coder", "bash")
        json_str = trail.export_json()
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_export_json_to_file(self, trail, tmp_path):
        trail.record("tool_call", "coder", "bash")
        output = tmp_path / "export.json"
        trail.export_json(output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert len(data) >= 1

    def test_export_includes_all_fields(self, trail):
        trail.record("tool_call", "coder", "bash", reasoning="test", outcome="success")
        json_str = trail.export_json()
        data = json.loads(json_str)[0]
        assert "event_id" in data
        assert "timestamp" in data
        assert "reasoning" in data
        assert data["outcome"] == "success"
