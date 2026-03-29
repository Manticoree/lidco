"""Tests for src/lidco/cli/commands/q124_cmds.py."""
from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q124_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg, mod


# ------------------------------------------------------------------ #
# /run registration                                                    #
# ------------------------------------------------------------------ #

class TestRunRegistered:
    def test_command_registered(self):
        reg, _ = _load()
        assert "run" in reg.commands

    def test_command_has_description(self):
        reg, _ = _load()
        cmd = reg.commands["run"]
        assert cmd.description


# ------------------------------------------------------------------ #
# /run demo                                                            #
# ------------------------------------------------------------------ #

class TestRunDemo:
    def test_demo_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("demo"))
        assert isinstance(result, str)

    def test_demo_mentions_tasks(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("demo"))
        assert "task" in result.lower() or "ran" in result.lower()

    def test_demo_shows_success_info(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("demo"))
        assert "succeed" in result.lower() or "ok" in result.lower() or "3" in result

    def test_demo_shows_success_rate(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("demo"))
        assert "%" in result or "rate" in result.lower()

    def test_demo_populates_tracker(self):
        reg, mod = _load()
        _run(reg.commands["run"].handler("demo"))
        tracker = mod._state.get("tracker")
        assert tracker is not None
        s = tracker.summary()
        assert s["total"] > 0


# ------------------------------------------------------------------ #
# /run status                                                          #
# ------------------------------------------------------------------ #

class TestRunStatus:
    def test_status_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("status"))
        assert isinstance(result, str)

    def test_status_shows_summary(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("status"))
        assert "total" in result.lower() or "summary" in result.lower()

    def test_status_after_demo(self):
        reg, _ = _load()
        _run(reg.commands["run"].handler("demo"))
        result = _run(reg.commands["run"].handler("status"))
        assert "total" in result.lower()
        # Should show at least some tasks tracked
        assert "3" in result or "done" in result.lower()


# ------------------------------------------------------------------ #
# /run pipeline                                                        #
# ------------------------------------------------------------------ #

class TestRunPipeline:
    def test_pipeline_returns_string(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("pipeline"))
        assert isinstance(result, str)

    def test_pipeline_shows_result(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("pipeline"))
        assert "result" in result.lower() or "output" in result.lower() or "HELLO" in result

    def test_pipeline_shows_steps_run(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("pipeline"))
        assert "step" in result.lower() or "3" in result

    def test_pipeline_shows_success(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("pipeline"))
        assert "success" in result.lower() or "true" in result.lower() or "True" in result


# ------------------------------------------------------------------ #
# /run unknown                                                         #
# ------------------------------------------------------------------ #

class TestRunUnknown:
    def test_unknown_returns_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler("unknown"))
        assert "Usage" in result or "usage" in result.lower()

    def test_no_args_returns_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["run"].handler(""))
        assert "Usage" in result or "demo" in result.lower()
