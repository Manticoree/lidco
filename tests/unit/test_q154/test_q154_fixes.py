"""Tests for Q154 bug-fix tasks (882–886)."""
from __future__ import annotations

import asyncio
import inspect
import unittest
from dataclasses import fields
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Task 882: AgentRegistry.register() accepts a single agent parameter
# ---------------------------------------------------------------------------
class TestAgentRegistryRegister(unittest.TestCase):
    """Task 882 — AgentRegistry.register(agent) works with a single param."""

    def _make_registry(self):
        from lidco.agents.registry import AgentRegistry
        return AgentRegistry()

    def _make_agent(self, name: str = "test-agent"):
        agent = MagicMock()
        agent.name = name
        return agent

    def test_register_single_agent(self):
        reg = self._make_registry()
        agent = self._make_agent("alpha")
        reg.register(agent)
        self.assertIs(reg.get("alpha"), agent)

    def test_register_returns_none(self):
        reg = self._make_registry()
        result = reg.register(self._make_agent())
        self.assertIsNone(result)

    def test_get_missing_returns_none(self):
        reg = self._make_registry()
        self.assertIsNone(reg.get("nonexistent"))

    def test_register_multiple_agents(self):
        reg = self._make_registry()
        a1 = self._make_agent("one")
        a2 = self._make_agent("two")
        reg.register(a1)
        reg.register(a2)
        self.assertIs(reg.get("one"), a1)
        self.assertIs(reg.get("two"), a2)

    def test_register_override_same_name(self):
        reg = self._make_registry()
        a1 = self._make_agent("x")
        a2 = self._make_agent("x")
        reg.register(a1)
        reg.register(a2)
        self.assertIs(reg.get("x"), a2)

    def test_list_agents_after_register(self):
        reg = self._make_registry()
        a = self._make_agent("bot")
        reg.register(a)
        self.assertIn(a, reg.list_agents())

    def test_list_names_after_register(self):
        reg = self._make_registry()
        reg.register(self._make_agent("agent-a"))
        reg.register(self._make_agent("agent-b"))
        names = reg.list_names()
        self.assertIn("agent-a", names)
        self.assertIn("agent-b", names)

    def test_register_signature_single_param(self):
        """register() signature accepts exactly one positional param (agent)."""
        from lidco.agents.registry import AgentRegistry
        sig = inspect.signature(AgentRegistry.register)
        # params: self, agent
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["self", "agent"])


# ---------------------------------------------------------------------------
# Task 883: CommandRegistry.register_async convenience method
# ---------------------------------------------------------------------------
class TestCommandRegistryRegisterAsync(unittest.TestCase):
    """Task 883 — CommandRegistry has register_async(name, desc, handler)."""

    def _make_registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        with patch.object(CommandRegistry, "_register_builtins", lambda self: None):
            return CommandRegistry()

    def test_register_async_exists(self):
        reg = self._make_registry()
        self.assertTrue(hasattr(reg, "register_async"))

    def test_register_async_creates_command(self):
        reg = self._make_registry()

        async def handler(args: str) -> str:
            return "ok"

        reg.register_async("my-cmd", "A test command", handler)
        cmd = reg.get("my-cmd")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "my-cmd")
        self.assertEqual(cmd.description, "A test command")
        self.assertIs(cmd.handler, handler)

    def test_register_async_callable_via_get(self):
        reg = self._make_registry()

        async def handler(args: str) -> str:
            return "hello"

        reg.register_async("greet", "Greet", handler)
        cmd = reg.get("greet")
        result = asyncio.run(cmd.handler(""))
        self.assertEqual(result, "hello")

    def test_register_async_overrides_existing(self):
        reg = self._make_registry()

        async def h1(args: str) -> str:
            return "v1"

        async def h2(args: str) -> str:
            return "v2"

        reg.register_async("cmd", "v1", h1)
        reg.register_async("cmd", "v2", h2)
        cmd = reg.get("cmd")
        self.assertEqual(cmd.description, "v2")
        self.assertEqual(asyncio.run(cmd.handler("")), "v2")

    def test_register_async_appears_in_list(self):
        reg = self._make_registry()

        async def h(args: str) -> str:
            return ""

        reg.register_async("listed", "Listed", h)
        names = [c.name for c in reg.list_commands()]
        self.assertIn("listed", names)


# ---------------------------------------------------------------------------
# Task 884: q91_cmds handlers are async (coroutine functions)
# ---------------------------------------------------------------------------
class TestQ91HandlersAsync(unittest.TestCase):
    """Task 884 — all q91_cmds handlers must be async coroutine functions."""

    def _get_registry_with_q91(self):
        from lidco.cli.commands.registry import CommandRegistry, SlashCommand
        with patch.object(CommandRegistry, "_register_builtins", lambda self: None):
            reg = CommandRegistry()
        from lidco.cli.commands.q91_cmds import register_q91_commands
        register_q91_commands(reg)
        return reg

    def test_session_history_handler_is_async(self):
        reg = self._get_registry_with_q91()
        cmd = reg.get("session-history")
        self.assertIsNotNone(cmd, "session-history command not registered")
        self.assertTrue(inspect.iscoroutinefunction(cmd.handler))

    def test_smart_apply_handler_is_async(self):
        reg = self._get_registry_with_q91()
        cmd = reg.get("smart-apply")
        self.assertIsNotNone(cmd)
        self.assertTrue(inspect.iscoroutinefunction(cmd.handler))

    def test_ignore_handler_is_async(self):
        reg = self._get_registry_with_q91()
        cmd = reg.get("ignore")
        self.assertIsNotNone(cmd)
        self.assertTrue(inspect.iscoroutinefunction(cmd.handler))

    def test_mem_compact_handler_is_async(self):
        reg = self._make_q91_reg()
        cmd = reg.get("mem-compact")
        self.assertIsNotNone(cmd)
        self.assertTrue(inspect.iscoroutinefunction(cmd.handler))

    def test_plugins_handler_is_async(self):
        reg = self._make_q91_reg()
        cmd = reg.get("plugins")
        self.assertIsNotNone(cmd)
        self.assertTrue(inspect.iscoroutinefunction(cmd.handler))

    def _make_q91_reg(self):
        return self._get_registry_with_q91()

    def test_all_q91_commands_registered(self):
        """All five Q91 commands exist."""
        reg = self._get_registry_with_q91()
        expected = ["session-history", "smart-apply", "ignore", "mem-compact", "plugins"]
        for name in expected:
            self.assertIsNotNone(reg.get(name), f"/{name} not registered")


# ---------------------------------------------------------------------------
# Task 885: English error / status messages (no Russian strings)
# ---------------------------------------------------------------------------
class TestEnglishMessages(unittest.TestCase):
    """Task 885 — session.py and base.py use English strings."""

    def test_session_error_ledger_message_english(self):
        """session.py contains the English ErrorLedger warning."""
        import lidco.core.session as session_mod
        source = inspect.getsource(session_mod)
        self.assertIn("ErrorLedger unavailable 3 times in a row", source)

    def test_base_agent_analysis_status(self):
        """base.py uses 'Analysis' for step 1 status."""
        import lidco.agents.base as base_mod
        source = inspect.getsource(base_mod)
        self.assertIn("Analysis", source)

    def test_base_agent_processing_status(self):
        """base.py uses 'Processing' for subsequent step status."""
        import lidco.agents.base as base_mod
        source = inspect.getsource(base_mod)
        self.assertIn("Processing", source)

    def test_no_russian_analysis_in_base(self):
        """base.py must not contain Russian 'Анализ' or 'Обработка'."""
        import lidco.agents.base as base_mod
        source = inspect.getsource(base_mod)
        self.assertNotIn("Анализ", source)
        self.assertNotIn("Обработка", source)


# ---------------------------------------------------------------------------
# Task 886: RestoreAction has content field; plan()/apply() use it
# ---------------------------------------------------------------------------
class TestRestorePlannerContent(unittest.TestCase):
    """Task 886 — RestoreAction.content is populated and used."""

    def test_restore_action_has_content_field(self):
        from lidco.workspace.restore_planner import RestoreAction
        field_names = [f.name for f in fields(RestoreAction)]
        self.assertIn("content", field_names)

    def test_restore_action_content_default_empty(self):
        from lidco.workspace.restore_planner import RestoreAction
        action = RestoreAction(path="a.py", action="write")
        self.assertEqual(action.content, "")

    def test_restore_action_content_set(self):
        from lidco.workspace.restore_planner import RestoreAction
        action = RestoreAction(path="a.py", action="write", content="hello")
        self.assertEqual(action.content, "hello")

    def test_plan_populates_content_from_snapshot(self):
        from lidco.workspace.restore_planner import RestorePlanner
        from lidco.workspace.snapshot2 import WorkspaceSnapshot, FileSnapshot
        from lidco.workspace.file_index import FileIndex

        snap = WorkspaceSnapshot(
            id="s1", label="test", created_at="2026-01-01T00:00:00",
            files={
                "a.py": FileSnapshot(path="a.py", content="print('a')", mtime=1.0, size=10),
            },
        )
        idx = FileIndex()
        # file not indexed => has_changed returns True => write action
        planner = RestorePlanner()
        actions = planner.plan(snap, idx)
        write_actions = [a for a in actions if a.action == "write"]
        self.assertEqual(len(write_actions), 1)
        self.assertEqual(write_actions[0].content, "print('a')")

    def test_plan_skip_unchanged(self):
        from lidco.workspace.restore_planner import RestorePlanner
        from lidco.workspace.snapshot2 import WorkspaceSnapshot, FileSnapshot
        from lidco.workspace.file_index import FileIndex

        content = "same content"
        snap = WorkspaceSnapshot(
            id="s2", label="test", created_at="2026-01-01T00:00:00",
            files={
                "b.py": FileSnapshot(path="b.py", content=content, mtime=1.0, size=12),
            },
        )
        idx = FileIndex()
        idx.index_file("b.py", content, mtime=1.0)

        planner = RestorePlanner()
        actions = planner.plan(snap, idx)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action, "skip")

    def test_plan_delete_extra_files(self):
        from lidco.workspace.restore_planner import RestorePlanner
        from lidco.workspace.snapshot2 import WorkspaceSnapshot
        from lidco.workspace.file_index import FileIndex

        snap = WorkspaceSnapshot(
            id="s3", label="empty", created_at="2026-01-01T00:00:00", files={},
        )
        idx = FileIndex()
        idx.index_file("extra.py", "data", mtime=1.0)

        planner = RestorePlanner()
        actions = planner.plan(snap, idx)
        del_actions = [a for a in actions if a.action == "delete"]
        self.assertEqual(len(del_actions), 1)
        self.assertEqual(del_actions[0].path, "extra.py")

    def test_apply_passes_content_to_write_fn(self):
        from lidco.workspace.restore_planner import RestorePlanner, RestoreAction

        written = {}

        def write_fn(path: str, content: str) -> None:
            written[path] = content

        def delete_fn(path: str) -> None:
            pass

        actions = [
            RestoreAction(path="f.py", action="write", content="file content here"),
        ]
        planner = RestorePlanner()
        results = planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(results["f.py"])
        self.assertEqual(written["f.py"], "file content here")

    def test_apply_skip_does_not_call_write(self):
        from lidco.workspace.restore_planner import RestorePlanner, RestoreAction

        write_fn = MagicMock()
        delete_fn = MagicMock()

        actions = [RestoreAction(path="x.py", action="skip")]
        planner = RestorePlanner()
        results = planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(results["x.py"])
        write_fn.assert_not_called()
        delete_fn.assert_not_called()

    def test_apply_delete_calls_delete_fn(self):
        from lidco.workspace.restore_planner import RestorePlanner, RestoreAction

        deleted = []

        def write_fn(path: str, content: str) -> None:
            pass

        def delete_fn(path: str) -> None:
            deleted.append(path)

        actions = [RestoreAction(path="gone.py", action="delete", reason="not in snapshot")]
        planner = RestorePlanner()
        results = planner.apply(actions, write_fn, delete_fn)
        self.assertTrue(results["gone.py"])
        self.assertEqual(deleted, ["gone.py"])

    def test_apply_write_failure_returns_false(self):
        from lidco.workspace.restore_planner import RestorePlanner, RestoreAction

        def write_fn(path: str, content: str) -> None:
            raise OSError("disk full")

        def delete_fn(path: str) -> None:
            pass

        actions = [RestoreAction(path="fail.py", action="write", content="data")]
        planner = RestorePlanner()
        results = planner.apply(actions, write_fn, delete_fn)
        self.assertFalse(results["fail.py"])


if __name__ == "__main__":
    unittest.main()
