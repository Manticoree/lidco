"""Tests for Q31 slash commands: /status, /retry, /undo."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from lidco.cli.commands import CommandRegistry


def _make_registry(session: object | None = None) -> CommandRegistry:
    registry = CommandRegistry()
    registry.set_session(session)
    return registry


# ── /status ──────────────────────────────────────────────────────────────────

class TestStatusCommand:
    def _make_session(self) -> MagicMock:
        sess = MagicMock()
        tb = MagicMock()
        tb._total_tokens = 5000
        tb._total_prompt_tokens = 4000
        tb._total_completion_tokens = 1000
        tb._total_cost_usd = 0.012
        tb._by_role = {"coder": 3000, "debugger": 2000}
        tb.session_limit = 0
        sess.token_budget = tb
        mem = MagicMock()
        mem.list_all.return_value = ["a", "b", "c"]
        sess.memory = mem
        tool_reg = MagicMock()
        tool_reg.list_tools.return_value = list(range(25))
        sess.tool_registry = tool_reg
        cfg = MagicMock()
        cfg.llm.default_model = "gpt-4"
        sess.config = cfg
        sess.debug_mode = False
        return sess

    @pytest.mark.asyncio
    async def test_status_shows_model(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "gpt-4" in result

    @pytest.mark.asyncio
    async def test_status_shows_tokens(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "5.0k" in result or "5000" in result

    @pytest.mark.asyncio
    async def test_status_shows_memory_count(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "3" in result  # 3 memory entries

    @pytest.mark.asyncio
    async def test_status_shows_tool_count(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "25" in result

    @pytest.mark.asyncio
    async def test_status_shows_cost(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "$" in result

    @pytest.mark.asyncio
    async def test_status_no_session(self):
        registry = _make_registry(None)
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "not initialized" in result.lower()

    @pytest.mark.asyncio
    async def test_status_debug_off(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "off" in result

    @pytest.mark.asyncio
    async def test_status_shows_per_agent_breakdown(self):
        registry = _make_registry(self._make_session())
        cmd = registry.get("status")
        result = await cmd.handler()
        assert "coder" in result
        assert "debugger" in result


# ── /retry ───────────────────────────────────────────────────────────────────

class TestRetryCommand:
    @pytest.mark.asyncio
    async def test_retry_with_last_message(self):
        registry = _make_registry()
        registry.last_message = "fix the bug"
        cmd = registry.get("retry")
        result = await cmd.handler()
        assert result == "__RETRY__:fix the bug"

    @pytest.mark.asyncio
    async def test_retry_with_arg_overrides(self):
        registry = _make_registry()
        registry.last_message = "old message"
        cmd = registry.get("retry")
        result = await cmd.handler(arg="new message")
        assert result == "__RETRY__:new message"

    @pytest.mark.asyncio
    async def test_retry_no_last_message(self):
        registry = _make_registry()
        registry.last_message = ""
        cmd = registry.get("retry")
        result = await cmd.handler()
        assert "Nothing to retry" in result

    @pytest.mark.asyncio
    async def test_retry_sentinel_prefix(self):
        registry = _make_registry()
        registry.last_message = "test"
        cmd = registry.get("retry")
        result = await cmd.handler()
        assert result.startswith("__RETRY__:")


# ── /undo ─────────────────────────────────────────────────────────────────────

class TestUndoCommand:
    @pytest.mark.asyncio
    async def test_undo_no_changes(self):
        registry = _make_registry()
        cmd = registry.get("undo")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            result = await cmd.handler()
        assert "No uncommitted" in result

    @pytest.mark.asyncio
    async def test_undo_shows_modified_files(self):
        registry = _make_registry()
        cmd = registry.get("undo")

        def fake_run(args, **kwargs):
            m = MagicMock()
            if "diff" in args:
                m.stdout = "src/foo.py\nsrc/bar.py\n"
            else:
                m.stdout = ""
            return m

        with patch("subprocess.run", side_effect=fake_run):
            result = await cmd.handler()
        assert "src/foo.py" in result
        assert "src/bar.py" in result
        assert "--force" in result  # should mention --force to confirm

    @pytest.mark.asyncio
    async def test_undo_force_restores(self):
        registry = _make_registry()
        cmd = registry.get("undo")
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            m = MagicMock()
            if "diff" in args:
                m.stdout = "src/foo.py\n"
            else:
                m.stdout = ""
            return m

        with patch("subprocess.run", side_effect=fake_run):
            result = await cmd.handler(arg="--force")

        restore_calls = [c for c in calls if "restore" in c]
        assert restore_calls, "git restore should have been called"
        assert "Restored" in result

    @pytest.mark.asyncio
    async def test_undo_shows_untracked_files(self):
        registry = _make_registry()
        cmd = registry.get("undo")

        def fake_run(args, **kwargs):
            m = MagicMock()
            if "diff" in args:
                m.stdout = ""
            else:
                m.stdout = "new_file.py\n"
            return m

        with patch("subprocess.run", side_effect=fake_run):
            result = await cmd.handler()
        assert "new_file.py" in result
