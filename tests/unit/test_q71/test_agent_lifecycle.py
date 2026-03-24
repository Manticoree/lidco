"""Tests for AgentLifecycleManager — T480."""
from __future__ import annotations
import pytest
from lidco.agents.lifecycle import AgentLifecycleManager, AgentLifecycleStatus, AgentRecord


class TestAgentLifecycleManager:
    def test_register(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        record = mgr.register("coder")
        assert record.name == "coder"
        assert record.status == AgentLifecycleStatus.IDLE

    def test_start(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("coder")
        assert mgr.start("coder")
        assert mgr.get("coder").status == AgentLifecycleStatus.RUNNING

    def test_pause(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("coder")
        mgr.start("coder")
        assert mgr.pause("coder")
        assert mgr.get("coder").status == AgentLifecycleStatus.PAUSED

    def test_resume(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("coder")
        mgr.start("coder")
        mgr.pause("coder")
        assert mgr.resume("coder")
        assert mgr.get("coder").status == AgentLifecycleStatus.RUNNING

    def test_kill(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("coder")
        mgr.start("coder")
        assert mgr.kill("coder")
        assert mgr.get("coder").status == AgentLifecycleStatus.TERMINATED

    def test_killed_agent_cannot_start(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("coder")
        mgr.kill("coder")
        assert not mgr.start("coder")

    def test_list_all(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("a")
        mgr.register("b")
        assert len(mgr.list_all()) == 2

    def test_persists_to_disk(self, tmp_path):
        mgr1 = AgentLifecycleManager(project_dir=tmp_path)
        mgr1.register("agent")
        mgr1.start("agent")
        mgr2 = AgentLifecycleManager(project_dir=tmp_path)
        record = mgr2.get("agent")
        assert record is not None
        assert record.status == AgentLifecycleStatus.RUNNING

    def test_pause_not_running_returns_false(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("a")
        assert not mgr.pause("a")

    def test_resume_not_paused_returns_false(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        mgr.register("a")
        mgr.start("a")
        assert not mgr.resume("a")

    def test_start_unregistered_auto_registers(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        assert mgr.start("new_agent")
        assert mgr.get("new_agent").status == AgentLifecycleStatus.RUNNING

    def test_kill_unknown_returns_false(self, tmp_path):
        mgr = AgentLifecycleManager(project_dir=tmp_path)
        assert not mgr.kill("nope")
