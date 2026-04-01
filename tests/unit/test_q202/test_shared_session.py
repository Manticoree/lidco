"""Tests for lidco.teams.shared_session."""

from __future__ import annotations

from lidco.teams.shared_session import CursorPosition, SessionMode, SharedSession


class TestSessionMode:
    def test_values(self) -> None:
        assert SessionMode.TURN_BASED == "turn_based"
        assert SessionMode.CONCURRENT == "concurrent"


class TestSharedSession:
    def test_join_and_active_users(self) -> None:
        s = SharedSession("t1")
        s.join("alice")
        s.join("bob")
        assert s.active_users() == ["alice", "bob"]
        assert s.user_count() == 2

    def test_join_duplicate_ignored(self) -> None:
        s = SharedSession("t1")
        s.join("alice")
        s.join("alice")
        assert s.user_count() == 1

    def test_leave(self) -> None:
        s = SharedSession("t1")
        s.join("alice")
        s.leave("alice")
        assert s.user_count() == 0

    def test_leave_nonexistent_safe(self) -> None:
        s = SharedSession("t1")
        s.leave("ghost")  # should not raise

    def test_cursor_update_and_get(self) -> None:
        s = SharedSession("t1")
        s.join("alice")
        s.update_cursor("alice", "main.py", 42, 10)
        cursors = s.get_cursors()
        assert len(cursors) == 1
        assert cursors[0] == CursorPosition("alice", "main.py", 42, 10)

    def test_is_turn_turn_based(self) -> None:
        s = SharedSession("t1", SessionMode.TURN_BASED)
        s.join("alice")
        s.join("bob")
        assert s.is_turn("alice") is True
        assert s.is_turn("bob") is False

    def test_next_turn(self) -> None:
        s = SharedSession("t1", SessionMode.TURN_BASED)
        s.join("alice")
        s.join("bob")
        result = s.next_turn()
        assert result == "bob"
        assert s.is_turn("bob") is True
        result2 = s.next_turn()
        assert result2 == "alice"

    def test_is_turn_concurrent_always_true(self) -> None:
        s = SharedSession("t1", SessionMode.CONCURRENT)
        s.join("alice")
        s.join("bob")
        assert s.is_turn("alice") is True
        assert s.is_turn("bob") is True

    def test_next_turn_empty(self) -> None:
        s = SharedSession("t1")
        assert s.next_turn() is None

    def test_leave_adjusts_turn(self) -> None:
        s = SharedSession("t1")
        s.join("a")
        s.join("b")
        s.next_turn()  # now b's turn, index=1
        s.leave("b")
        # Should reset index and not crash
        assert s.user_count() == 1
