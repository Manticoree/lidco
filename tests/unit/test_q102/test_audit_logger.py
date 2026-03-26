"""Tests for src/lidco/audit/logger.py — AuditLogger."""
import json
import time
import pytest
from lidco.audit.logger import AuditLogger, AuditEntry


class TestAuditLoggerBasic:
    def setup_method(self):
        self.al = AuditLogger(path=None)

    def test_log_creates_entry(self):
        entry = self.al.log("alice", "login", "/auth")
        assert isinstance(entry, AuditEntry)
        assert entry.actor == "alice"
        assert entry.action == "login"
        assert entry.resource == "/auth"
        assert entry.outcome == "success"

    def test_log_invalid_outcome(self):
        with pytest.raises(ValueError):
            self.al.log("alice", "login", "/auth", outcome="invalid")

    def test_log_failure_outcome(self):
        entry = self.al.log("bob", "access", "/secret", outcome="failure")
        assert entry.outcome == "failure"

    def test_log_denied_outcome(self):
        entry = self.al.log("charlie", "delete", "/file", outcome="denied")
        assert entry.outcome == "denied"

    def test_entry_has_id(self):
        entry = self.al.log("alice", "act", "res")
        assert len(entry.id) > 0

    def test_entry_has_timestamp(self):
        before = time.time()
        entry = self.al.log("alice", "act", "res")
        after = time.time()
        assert before <= entry.timestamp <= after

    def test_entry_has_session_id(self):
        entry = self.al.log("alice", "act", "res")
        assert entry.session_id == self.al.session_id

    def test_count(self):
        assert self.al.count() == 0
        self.al.log("a", "b", "c")
        assert self.al.count() == 1

    def test_all_oldest_first(self):
        self.al.log("a", "first", "r")
        time.sleep(0.01)
        self.al.log("a", "second", "r")
        entries = self.al.all()
        assert entries[0].action == "first"
        assert entries[1].action == "second"

    def test_clear(self):
        self.al.log("a", "b", "c")
        n = self.al.clear()
        assert n == 1
        assert self.al.count() == 0

    def test_details_stored(self):
        entry = self.al.log("a", "b", "c", details={"key": "val"})
        assert entry.details == {"key": "val"}


class TestAuditLoggerQuery:
    def setup_method(self):
        self.al = AuditLogger(path=None)
        self.al.log("alice", "read", "/files/a")
        self.al.log("bob", "write", "/files/b", outcome="failure")
        self.al.log("alice", "delete", "/files/c", outcome="denied")

    def test_query_all(self):
        results = self.al.query()
        assert len(results) == 3

    def test_query_by_actor(self):
        results = self.al.query(actor="alice")
        assert all(e.actor == "alice" for e in results)
        assert len(results) == 2

    def test_query_by_outcome(self):
        results = self.al.query(outcome="failure")
        assert len(results) == 1
        assert results[0].outcome == "failure"

    def test_query_by_resource(self):
        results = self.al.query(resource="/files/a")
        assert len(results) == 1

    def test_query_by_action(self):
        results = self.al.query(action="read")
        assert len(results) == 1

    def test_query_newest_first(self):
        results = self.al.query()
        ts = [e.timestamp for e in results]
        assert ts == sorted(ts, reverse=True)

    def test_query_limit(self):
        results = self.al.query(limit=2)
        assert len(results) == 2

    def test_query_since(self):
        future = time.time() + 1000
        results = self.al.query(since=future)
        assert len(results) == 0

    def test_query_until(self):
        past = time.time() - 1000
        results = self.al.query(until=past)
        assert len(results) == 0


class TestAuditLoggerExport:
    def setup_method(self):
        self.al = AuditLogger(path=None)
        self.al.log("alice", "login", "/auth")

    def test_export_json(self):
        data = json.loads(self.al.export_json())
        assert isinstance(data, list)
        assert data[0]["actor"] == "alice"

    def test_export_csv(self):
        csv_str = self.al.export_csv()
        assert "alice" in csv_str
        assert "actor" in csv_str

    def test_export_csv_has_header(self):
        csv_str = self.al.export_csv()
        lines = csv_str.strip().splitlines()
        assert "actor" in lines[0]


class TestAuditLoggerPersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "audit.json"
        al1 = AuditLogger(path=path)
        al1.log("alice", "login", "/auth")

        al2 = AuditLogger(path=path)
        assert al2.count() == 1
        entries = al2.all()
        assert entries[0].actor == "alice"

    def test_reload_method(self, tmp_path):
        path = tmp_path / "audit.json"
        al1 = AuditLogger(path=path)
        al1.log("alice", "login", "/auth")

        al2 = AuditLogger(path=path)
        al1.log("bob", "logout", "/auth")

        al2.reload()
        assert al2.count() == 2

    def test_max_entries_truncated(self):
        al = AuditLogger(path=None, max_entries=3)
        for i in range(10):
            al.log(f"u{i}", "act", "res")
        assert al.count() == 3
