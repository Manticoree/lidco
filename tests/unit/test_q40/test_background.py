"""Tests for Q40 — BackgroundTaskManager (Task 270)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.background import BackgroundAgent, BackgroundTaskManager


@pytest.fixture()
def mock_session():
    session = MagicMock()
    session.get_full_context.return_value = "ctx"
    response = MagicMock()
    response.content = "done"
    session.orchestrator.handle = AsyncMock(return_value=response)
    return session


@pytest.fixture()
def manager():
    return BackgroundTaskManager()


class TestBackgroundTaskManager:
    def test_submit_returns_task_id(self, mock_session):
        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("do something", mock_session)
            assert isinstance(task_id, str)
            assert len(task_id) == 8

        asyncio.run(run())

    def test_submit_shows_running_status(self, mock_session):
        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("task", mock_session)
            bg = mgr.get(task_id)
            assert bg is not None
            assert bg.status == "running"

        asyncio.run(run())

    def test_get_nonexistent_returns_none(self, manager):
        assert manager.get("nope") is None

    def test_list_all_empty_initially(self, manager):
        assert manager.list_all() == []

    def test_running_count_zero_initially(self, manager):
        assert manager.running_count() == 0

    def test_cancel_unknown_task_returns_false(self, manager):
        assert manager.cancel("unknown") is False

    def test_background_agent_fields(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        bg = BackgroundAgent(
            task_id="abc",
            task="do stuff",
            agent_name="coder",
            started_at=now,
        )
        assert bg.task_id == "abc"
        assert bg.task == "do stuff"
        assert bg.agent_name == "coder"
        assert bg.status == "running"
        assert bg.result is None
        assert bg.error is None
        assert bg.finished_at is None
        assert bg.worktree_branch is None

    def test_notification_callback_set(self, manager):
        cb = MagicMock()
        manager.set_notification_callback(cb)
        assert manager._notification_callback is cb

    def test_task_completes_and_moves_to_done(self, mock_session):
        """Test that a submitted task can complete successfully."""
        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("task", mock_session)
            # Wait for the asyncio task to complete
            await asyncio.sleep(0.05)
            bg = mgr.get(task_id)
            return bg

        bg = asyncio.run(run())
        assert bg is not None
        assert bg.status == "done"
        assert bg.finished_at is not None

    def test_failed_task_marked_failed(self):
        async def run():
            session = MagicMock()
            session.get_full_context.return_value = ""
            session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("oops"))
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("bad task", session)
            await asyncio.sleep(0.05)
            return mgr.get(task_id)

        bg = asyncio.run(run())
        assert bg is not None
        assert bg.status == "failed"
        assert "oops" in (bg.error or "")

    def test_list_running_and_done(self, mock_session):
        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("task", mock_session)
            # Before completion
            running = mgr.list_running()
            assert any(b.task_id == task_id for b in running)
            # After completion
            await asyncio.sleep(0.05)
            done = mgr.list_done()
            assert any(b.task_id == task_id for b in done)
            return True

        assert asyncio.run(run())

    def test_collect_done_removes_from_registry(self, mock_session):
        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("task", mock_session)
            await asyncio.sleep(0.05)
            done = mgr.collect_done()
            assert any(b.task_id == task_id for b in done)
            # Now it should be gone
            assert mgr.get(task_id) is None
            return True

        assert asyncio.run(run())

    def test_cancel_running_task(self, mock_session):
        slow_session = MagicMock()
        slow_session.get_full_context.return_value = ""

        async def slow_handle(*a, **kw):
            await asyncio.sleep(10)
            return MagicMock(content="done")

        slow_session.orchestrator.handle = slow_handle

        async def run():
            mgr = BackgroundTaskManager()
            task_id = mgr.submit("slow task", slow_session)
            await asyncio.sleep(0.01)  # let it start
            cancelled = mgr.cancel(task_id)
            await asyncio.sleep(0.05)
            bg = mgr.get(task_id)
            return cancelled, bg

        cancelled, bg = asyncio.run(run())
        assert cancelled is True

    def test_notification_callback_fired_on_completion(self, mock_session):
        notifications: list = []

        async def run():
            mgr = BackgroundTaskManager()
            mgr.set_notification_callback(lambda bg: notifications.append(bg))
            mgr.submit("task", mock_session)
            await asyncio.sleep(0.05)
            return True

        asyncio.run(run())
        assert len(notifications) == 1
        assert notifications[0].status == "done"
