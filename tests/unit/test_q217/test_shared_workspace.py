"""Tests for SharedWorkspace — room-based collaboration."""

from lidco.collab.shared_workspace import (
    SharedWorkspace,
    RoomStatus,
    Participant,
    FileLock,
    ActivityEntry,
)


class TestSharedWorkspaceInit:
    def test_default_name_uses_room_id(self):
        ws = SharedWorkspace(room_id="rm-1")
        assert ws.name == "rm-1"
        assert ws.room_id == "rm-1"

    def test_custom_name(self):
        ws = SharedWorkspace(room_id="rm-1", name="My Room")
        assert ws.name == "My Room"

    def test_initial_status_is_open(self):
        ws = SharedWorkspace(room_id="r")
        assert ws.status == RoomStatus.OPEN


class TestParticipants:
    def test_add_participant(self):
        ws = SharedWorkspace(room_id="r")
        p = ws.add_participant("u1", "Alice")
        assert isinstance(p, Participant)
        assert p.user_id == "u1"
        assert p.name == "Alice"
        assert p.role == "editor"

    def test_add_participant_custom_role(self):
        ws = SharedWorkspace(room_id="r")
        p = ws.add_participant("u1", "Alice", role="viewer")
        assert p.role == "viewer"

    def test_get_participants(self):
        ws = SharedWorkspace(room_id="r")
        ws.add_participant("u1", "A")
        ws.add_participant("u2", "B")
        assert len(ws.get_participants()) == 2

    def test_remove_participant(self):
        ws = SharedWorkspace(room_id="r")
        ws.add_participant("u1", "A")
        assert ws.remove_participant("u1") is True
        assert len(ws.get_participants()) == 0

    def test_remove_nonexistent_participant(self):
        ws = SharedWorkspace(room_id="r")
        assert ws.remove_participant("ghost") is False

    def test_remove_participant_releases_locks(self):
        ws = SharedWorkspace(room_id="r")
        ws.add_participant("u1", "A")
        ws.lock_file("a.py", "u1")
        ws.remove_participant("u1")
        assert ws.get_locks() == []


class TestFileLocking:
    def test_lock_file(self):
        ws = SharedWorkspace(room_id="r")
        lock = ws.lock_file("f.py", "u1")
        assert isinstance(lock, FileLock)
        assert lock.file_path == "f.py"
        assert lock.owner == "u1"

    def test_lock_conflict_returns_none(self):
        ws = SharedWorkspace(room_id="r")
        ws.lock_file("f.py", "u1")
        result = ws.lock_file("f.py", "u2")
        assert result is None

    def test_same_owner_can_relock(self):
        ws = SharedWorkspace(room_id="r")
        ws.lock_file("f.py", "u1")
        lock = ws.lock_file("f.py", "u1")
        assert lock is not None

    def test_unlock_file(self):
        ws = SharedWorkspace(room_id="r")
        ws.lock_file("f.py", "u1")
        assert ws.unlock_file("f.py", "u1") is True
        assert ws.get_locks() == []

    def test_unlock_wrong_owner(self):
        ws = SharedWorkspace(room_id="r")
        ws.lock_file("f.py", "u1")
        assert ws.unlock_file("f.py", "u2") is False

    def test_unlock_nonexistent(self):
        ws = SharedWorkspace(room_id="r")
        assert ws.unlock_file("f.py", "u1") is False

    def test_detect_conflicts_no_lock(self):
        ws = SharedWorkspace(room_id="r")
        assert ws.detect_conflicts("f.py", ["u1", "u2"]) == []

    def test_detect_conflicts_with_lock(self):
        ws = SharedWorkspace(room_id="r")
        ws.lock_file("f.py", "u1")
        conflicts = ws.detect_conflicts("f.py", ["u1", "u2", "u3"])
        assert conflicts == ["u2", "u3"]


class TestActivity:
    def test_log_and_get_activity(self):
        ws = SharedWorkspace(room_id="r")
        ws.log_activity("u1", "edit", "f.py")
        entries = ws.get_activity()
        assert len(entries) == 1
        assert entries[0].user_id == "u1"
        assert entries[0].action == "edit"
        assert entries[0].target == "f.py"

    def test_activity_limit(self):
        ws = SharedWorkspace(room_id="r")
        for i in range(10):
            ws.log_activity("u1", f"action-{i}")
        assert len(ws.get_activity(limit=3)) == 3


class TestCloseAndSummary:
    def test_close(self):
        ws = SharedWorkspace(room_id="r")
        ws.close()
        assert ws.status == RoomStatus.CLOSED

    def test_summary_contains_info(self):
        ws = SharedWorkspace(room_id="r", name="Test")
        ws.add_participant("u1", "A")
        s = ws.summary()
        assert "Test" in s
        assert "Participants: 1" in s
        assert "open" in s
