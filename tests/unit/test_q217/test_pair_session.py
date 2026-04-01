"""Tests for PairSession — pair programming with driver/navigator roles."""

from lidco.collab.pair_session import (
    PairSession,
    PairMember,
    SessionRole,
)


class TestPairSessionInit:
    def test_creator_becomes_driver(self):
        ps = PairSession(session_id="s1", creator="alice")
        driver = ps.get_driver()
        assert driver is not None
        assert driver.user_id == "alice"
        assert driver.role == SessionRole.DRIVER

    def test_session_starts_active(self):
        ps = PairSession(session_id="s1", creator="alice")
        assert ps.active is True

    def test_session_id_stored(self):
        ps = PairSession(session_id="my-session", creator="u")
        assert ps.session_id == "my-session"


class TestJoinLeave:
    def test_join(self):
        ps = PairSession(session_id="s", creator="a")
        m = ps.join("b", "Bob")
        assert isinstance(m, PairMember)
        assert m.role == SessionRole.NAVIGATOR

    def test_join_as_observer(self):
        ps = PairSession(session_id="s", creator="a")
        m = ps.join("b", "Bob", SessionRole.OBSERVER)
        assert m.role == SessionRole.OBSERVER

    def test_get_members(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob")
        assert len(ps.get_members()) == 2

    def test_leave(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob")
        assert ps.leave("b") is True
        assert len(ps.get_members()) == 1

    def test_leave_nonexistent(self):
        ps = PairSession(session_id="s", creator="a")
        assert ps.leave("ghost") is False


class TestRoleSwap:
    def test_swap_roles(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob")
        ps.swap_roles()
        driver = ps.get_driver()
        assert driver is not None
        assert driver.user_id == "b"

    def test_swap_preserves_observers(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob", SessionRole.OBSERVER)
        ps.swap_roles()
        members = {m.user_id: m for m in ps.get_members()}
        assert members["b"].role == SessionRole.OBSERVER

    def test_set_driver(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob")
        assert ps.set_driver("b") is True
        driver = ps.get_driver()
        assert driver.user_id == "b"

    def test_set_driver_demotes_old_driver(self):
        ps = PairSession(session_id="s", creator="a")
        ps.join("b", "Bob")
        ps.set_driver("b")
        members = {m.user_id: m for m in ps.get_members()}
        assert members["a"].role == SessionRole.NAVIGATOR

    def test_set_driver_nonexistent(self):
        ps = PairSession(session_id="s", creator="a")
        assert ps.set_driver("ghost") is False


class TestTurnHistory:
    def test_record_and_get(self):
        ps = PairSession(session_id="s", creator="a")
        ps.record_turn("a", "typed code")
        history = ps.get_turn_history()
        assert len(history) == 1
        assert history[0]["action"] == "typed code"

    def test_history_limit(self):
        ps = PairSession(session_id="s", creator="a")
        for i in range(30):
            ps.record_turn("a", f"action-{i}")
        assert len(ps.get_turn_history(limit=5)) == 5


class TestEndAndSummary:
    def test_end_session(self):
        ps = PairSession(session_id="s", creator="a")
        ps.end()
        assert ps.active is False

    def test_summary(self):
        ps = PairSession(session_id="s", creator="alice")
        s = ps.summary()
        assert "Session: s" in s
        assert "Active: True" in s
        assert "Driver: alice" in s
