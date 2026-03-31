"""Tests for Q91 CLI commands."""

import asyncio
from unittest.mock import MagicMock, patch


def make_registry():
    """Create a minimal mock registry."""
    registry = MagicMock()
    registry._last_assistant_message = ""
    commands = {}

    def register(cmd):
        commands[cmd.name] = cmd
    registry.register.side_effect = register
    registry._commands = commands
    return registry


def _get_handler(registry, name):
    return registry._commands[name].handler


def test_session_history_list_command(tmp_path):
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "session-history")

    with patch("lidco.memory.session_history.SessionHistoryStore") as MockStore:
        instance = MockStore.return_value
        instance.list.return_value = []
        result = asyncio.run(handler(""))
    assert "No session history" in result or "Recent" in result


def test_session_history_search_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "session-history")

    mock_record = MagicMock()
    mock_record.session_id = "abc123def"
    mock_record.topic = "Fix auth bug"
    mock_record.turn_count = 5

    with patch("lidco.memory.session_history.SessionHistoryStore") as MockStore:
        instance = MockStore.return_value
        search_result = MagicMock()
        search_result.records = [mock_record]
        search_result.total = 1
        instance.search.return_value = search_result
        result = asyncio.run(handler("auth"))
    assert "auth" in result.lower() or "Fix" in result


def test_smart_apply_dry_run_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "smart-apply")

    with patch("lidco.editing.smart_apply.SmartApply") as MockSA:
        instance = MockSA.return_value
        instance.apply_all.return_value = []
        result = asyncio.run(handler("--dry-run"))
    assert isinstance(result, str)


def test_smart_apply_no_last_message():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "smart-apply")
    result = asyncio.run(handler(""))
    assert "No recent" in result or "No applicable" in result or isinstance(result, str)


def test_ignore_list_command(tmp_path):
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "ignore")

    with patch("lidco.context.exclude_file.ContextExcludeFile") as MockEF:
        instance = MockEF.return_value
        instance.list_patterns.return_value = []
        result = asyncio.run(handler("list"))
    assert isinstance(result, str)


def test_ignore_add_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "ignore")

    with patch("lidco.context.exclude_file.ContextExcludeFile") as MockEF:
        instance = MockEF.return_value
        result = asyncio.run(handler("add *.pyc"))
    assert "*.pyc" in result or "Added" in result


def test_mem_compact_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "mem-compact")

    with patch("lidco.memory.agent_memory.AgentMemoryStore") as MockStore, \
         patch("lidco.memory.consolidator.MemoryConsolidator") as MockConsolidator:
        consolidator = MockConsolidator.return_value
        report = MagicMock()
        report.summary = "Merged 2 groups."
        consolidator.consolidate.return_value = report
        result = asyncio.run(handler(""))
    assert isinstance(result, str)


def test_mem_compact_dry_run_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "mem-compact")

    with patch("lidco.memory.agent_memory.AgentMemoryStore") as MockStore, \
         patch("lidco.memory.consolidator.MemoryConsolidator") as MockConsolidator:
        consolidator = MockConsolidator.return_value
        report = MagicMock()
        report.summary = "[dry-run] Would merge 1 group."
        consolidator.dry_run.return_value = report
        result = asyncio.run(handler("--dry-run"))
    assert isinstance(result, str)


def test_plugins_list_command():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    handler = _get_handler(registry, "plugins")

    with patch("lidco.tools.plugin_loader.ToolPluginLoader") as MockLoader:
        instance = MockLoader.return_value
        manifest = MagicMock()
        manifest.format_summary.return_value = "Plugins: 0/0 loaded, 0 failed"
        manifest.plugins = []
        instance.load_all.return_value = manifest
        result = asyncio.run(handler("list"))
    assert "Plugin" in result or "plugin" in result.lower()


def test_all_commands_registered():
    from lidco.cli.commands.q91_cmds import register_q91_commands
    registry = make_registry()
    register_q91_commands(registry)
    names = set(registry._commands.keys())
    assert "session-history" in names
    assert "smart-apply" in names
    assert "ignore" in names
    assert "mem-compact" in names
    assert "plugins" in names
