"""Tests for Q221 CLI commands."""
from __future__ import annotations

import asyncio

from lidco.cli.commands.q221_cmds import register


class _FakeRegistry:
    """Minimal stand-in for CommandRegistry."""

    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[getattr(cmd, "name", "")] = cmd


def _run(handler, args: str = "") -> str:
    return asyncio.run(handler(args))


class TestQ221CmdsRegistration:
    def test_registers_four_commands(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        expected = {"stream-mode", "stream-replay", "stream-export", "progress"}
        assert expected == set(reg.commands.keys())


class TestStreamModeCmd:
    def test_no_args(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-mode"].handler  # type: ignore[union-attr]
        result = _run(handler, "")
        assert "Usage" in result

    def test_list(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-mode"].handler  # type: ignore[union-attr]
        result = _run(handler, "list")
        assert "FanOutMultiplexer" in result

    def test_add(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-mode"].handler  # type: ignore[union-attr]
        result = _run(handler, "add myterm terminal")
        assert "Added" in result


class TestStreamReplayCmd:
    def test_start_stop(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-replay"].handler  # type: ignore[union-attr]
        assert "Recording started" in _run(handler, "start")
        assert "stopped" in _run(handler, "stop")

    def test_summary(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-replay"].handler  # type: ignore[union-attr]
        result = _run(handler, "")
        assert "EventReplay" in result


class TestStreamExportCmd:
    def test_empty_export(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["stream-export"].handler  # type: ignore[union-attr]
        result = _run(handler, "")
        assert "No events" in result


class TestProgressCmd:
    def test_no_args(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["progress"].handler  # type: ignore[union-attr]
        result = _run(handler, "")
        assert "No progress" in result

    def test_start(self) -> None:
        reg = _FakeRegistry()
        register(reg)
        handler = reg.commands["progress"].handler  # type: ignore[union-attr]
        result = _run(handler, "start build 100")
        assert "Started" in result
        assert "build" in result
