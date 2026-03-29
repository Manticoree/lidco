"""Tests for AgentTeamRegistry (Task 712)."""
from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock

from lidco.agents.team_registry import AgentTeam, AgentTeamRegistry, TeamNotFoundError


class TestAgentTeam(unittest.TestCase):
    def test_create_team(self):
        team = AgentTeam(name="alpha", roles={"dev": "writes code"})
        self.assertEqual(team.name, "alpha")
        self.assertEqual(team.roles["dev"], "writes code")
        self.assertIsNone(team.mailbox)

    def test_create_team_with_mailbox(self):
        mb = MagicMock()
        team = AgentTeam(name="beta", roles={}, mailbox=mb)
        self.assertIs(team.mailbox, mb)

    def test_team_empty_roles(self):
        team = AgentTeam(name="empty", roles={})
        self.assertEqual(len(team.roles), 0)

    def test_team_multiple_roles(self):
        roles = {"dev": "codes", "reviewer": "reviews", "tester": "tests"}
        team = AgentTeam(name="full", roles=roles)
        self.assertEqual(len(team.roles), 3)


class TestAgentTeamRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = AgentTeamRegistry()

    def test_register_and_get(self):
        team = AgentTeam(name="t1", roles={"a": "desc"})
        self.reg.register(team)
        got = self.reg.get("t1")
        self.assertEqual(got.name, "t1")

    def test_get_missing_raises(self):
        with self.assertRaises(TeamNotFoundError):
            self.reg.get("nonexistent")

    def test_register_overwrites(self):
        t1 = AgentTeam(name="t1", roles={"a": "old"})
        t2 = AgentTeam(name="t1", roles={"b": "new"})
        self.reg.register(t1)
        self.reg.register(t2)
        got = self.reg.get("t1")
        self.assertIn("b", got.roles)
        self.assertNotIn("a", got.roles)

    def test_list_all_empty(self):
        self.assertEqual(self.reg.list_all(), [])

    def test_list_all_multiple(self):
        self.reg.register(AgentTeam(name="a", roles={}))
        self.reg.register(AgentTeam(name="b", roles={}))
        self.assertEqual(len(self.reg.list_all()), 2)

    def test_unregister(self):
        self.reg.register(AgentTeam(name="x", roles={}))
        self.reg.unregister("x")
        with self.assertRaises(TeamNotFoundError):
            self.reg.get("x")

    def test_unregister_missing_raises(self):
        with self.assertRaises(TeamNotFoundError):
            self.reg.unregister("ghost")

    def test_broadcast_with_mailbox(self):
        mb = MagicMock()
        team = AgentTeam(name="t", roles={"dev": "d", "qa": "q"}, mailbox=mb)
        self.reg.register(team)
        count = self.reg.broadcast("t", "hello")
        self.assertEqual(count, 2)
        mb.broadcast.assert_called_once()

    def test_broadcast_no_mailbox(self):
        team = AgentTeam(name="t", roles={"dev": "d"})
        self.reg.register(team)
        count = self.reg.broadcast("t", "hello")
        self.assertEqual(count, 0)

    def test_broadcast_empty_roles(self):
        mb = MagicMock()
        team = AgentTeam(name="t", roles={}, mailbox=mb)
        self.reg.register(team)
        count = self.reg.broadcast("t", "hello")
        self.assertEqual(count, 0)

    def test_broadcast_custom_sender(self):
        mb = MagicMock()
        team = AgentTeam(name="t", roles={"dev": "d"}, mailbox=mb)
        self.reg.register(team)
        self.reg.broadcast("t", "hi", sender="boss")
        mb.broadcast.assert_called_once_with(from_="boss", message="hi", recipients=["dev"])

    def test_broadcast_missing_team_raises(self):
        with self.assertRaises(TeamNotFoundError):
            self.reg.broadcast("nope", "hello")

    def test_error_message_contains_name(self):
        try:
            self.reg.get("missing_team")
        except TeamNotFoundError as exc:
            self.assertIn("missing_team", str(exc))

    def test_thread_safety_register(self):
        """Concurrent registrations should not crash."""
        errors = []

        def register_team(i):
            try:
                self.reg.register(AgentTeam(name=f"team_{i}", roles={"r": "d"}))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_team, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.reg.list_all()), 20)

    def test_register_returns_none(self):
        result = self.reg.register(AgentTeam(name="a", roles={}))
        self.assertIsNone(result)

    def test_unregister_returns_none(self):
        self.reg.register(AgentTeam(name="a", roles={}))
        result = self.reg.unregister("a")
        self.assertIsNone(result)

    def test_list_all_after_unregister(self):
        self.reg.register(AgentTeam(name="a", roles={}))
        self.reg.register(AgentTeam(name="b", roles={}))
        self.reg.unregister("a")
        names = [t.name for t in self.reg.list_all()]
        self.assertNotIn("a", names)
        self.assertIn("b", names)

    def test_get_returns_same_object(self):
        team = AgentTeam(name="same", roles={"x": "y"})
        self.reg.register(team)
        self.assertIs(self.reg.get("same"), team)

    def test_register_preserves_mailbox(self):
        mb = MagicMock()
        team = AgentTeam(name="t", roles={}, mailbox=mb)
        self.reg.register(team)
        self.assertIs(self.reg.get("t").mailbox, mb)

    def test_broadcast_default_sender(self):
        mb = MagicMock()
        team = AgentTeam(name="t", roles={"dev": "d"}, mailbox=mb)
        self.reg.register(team)
        self.reg.broadcast("t", "msg")
        mb.broadcast.assert_called_once_with(from_="coordinator", message="msg", recipients=["dev"])

    def test_team_not_found_error_is_exception(self):
        self.assertTrue(issubclass(TeamNotFoundError, Exception))

    def test_multiple_overwrite_keeps_last(self):
        for i in range(5):
            self.reg.register(AgentTeam(name="x", roles={"v": str(i)}))
        self.assertEqual(self.reg.get("x").roles["v"], "4")


if __name__ == "__main__":
    unittest.main()
