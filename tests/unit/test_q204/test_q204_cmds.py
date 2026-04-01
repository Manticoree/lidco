"""Tests for lidco.cli.commands.q204_cmds."""
from __future__ import annotations

import asyncio

from lidco.cli.commands.q204_cmds import register, _state
from lidco.cli.commands.registry import CommandRegistry


def _fresh_registry() -> CommandRegistry:
    _state.clear()
    reg = CommandRegistry()
    register(reg)
    return reg


class TestQ204Commands:
    def test_transcript_usage(self):
        reg = _fresh_registry()
        cmd = reg._commands["transcript"]
        result = asyncio.run(cmd.handler(""))
        assert "Usage" in result

    def test_transcript_count_empty(self):
        reg = _fresh_registry()
        cmd = reg._commands["transcript"]
        result = asyncio.run(cmd.handler("count"))
        assert "0" in result

    def test_transcript_search_no_query(self):
        reg = _fresh_registry()
        cmd = reg._commands["transcript-search"]
        result = asyncio.run(cmd.handler(""))
        assert "Usage" in result

    def test_timeline_summary(self):
        reg = _fresh_registry()
        cmd = reg._commands["timeline"]
        result = asyncio.run(cmd.handler("summary"))
        assert "Empty" in result or "timeline" in result.lower()

    def test_transcript_export_empty(self):
        reg = _fresh_registry()
        cmd = reg._commands["transcript-export"]
        result = asyncio.run(cmd.handler("text"))
        assert "empty" in result.lower() or "Nothing" in result
