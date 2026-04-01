"""Tests for Q217 CLI commands: /collab, /review, /pair-session, /knowledge."""

import asyncio

from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _make_registry():
    """Create a minimal registry with only Q217 commands."""
    from lidco.cli.commands.q217_cmds import register

    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    register(reg)
    return reg


class TestCollabCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg._commands.get("collab") is not None

    def test_no_args_usage(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["collab"].handler(""))
        assert "Usage" in result

    def test_creates_room(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["collab"].handler("my-room"))
        assert "my-room" in result
        assert "Participants: 1" in result


class TestReviewCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg._commands.get("review") is not None

    def test_no_args_usage(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["review"].handler(""))
        assert "Usage" in result

    def test_missing_colon_usage(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["review"].handler("nocolon"))
        assert "Usage" in result

    def test_bad_line_number(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["review"].handler("f.py:abc comment"))
        assert "number" in result.lower()

    def test_valid_review(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["review"].handler("f.py:10 Fix bug"))
        assert "pending" in result
        assert "Threads: 1" in result


class TestPairSessionCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg._commands.get("pair-session") is not None

    def test_no_args_usage(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler(""))
        assert "Usage" in result

    def test_create(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler("create my-pair"))
        assert "my-pair" in result
        assert "Active: True" in result

    def test_join(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler("join bob"))
        assert "Members: 2" in result

    def test_swap(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler("swap"))
        assert "Driver:" in result

    def test_end(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler("end"))
        assert "Active: False" in result

    def test_unknown_action(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["pair-session"].handler("badaction"))
        assert "Unknown" in result


class TestKnowledgeCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg._commands.get("knowledge") is not None

    def test_no_args_usage(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler(""))
        assert "Usage" in result

    def test_add_with_pipe(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("add My Title | body here"))
        assert "My Title" in result

    def test_add_without_pipe(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("add JustTitle"))
        assert "JustTitle" in result

    def test_search_no_query(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("search"))
        assert "Usage" in result

    def test_search_no_results(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("search zzzzz"))
        assert "No snippets found" in result

    def test_top_empty(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("top"))
        assert "No snippets yet" in result

    def test_unknown_action(self):
        reg = _make_registry()
        result = asyncio.run(reg._commands["knowledge"].handler("badaction"))
        assert "Unknown" in result
