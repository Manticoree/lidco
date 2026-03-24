"""Tests for /arena CLI commands (T529)."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

import lidco.cli.commands.arena_cmds as acmds
from lidco.cli.commands.arena_cmds import (
    arena_compare_handler,
    arena_leaderboard_handler,
    arena_vote_handler,
    register_arena_commands,
)


def run(coro):
    return asyncio.run(coro)


def reset():
    acmds._last_arena_result = None
    acmds._leaderboard = None


# ---- /arena compare ----

def test_arena_compare_missing_args():
    result = run(arena_compare_handler("model-a"))
    assert "Usage" in result


def test_arena_compare_runs(monkeypatch):
    reset()
    mock_arena = MagicMock()
    mock_result = MagicMock()
    mock_entry = MagicMock()
    mock_entry.model = "model-a"
    mock_result.entries = [mock_entry, MagicMock()]
    mock_result.task = "test task"
    mock_arena.run.return_value = mock_result
    mock_arena.format_comparison.return_value = "| Model | Tokens |"

    with patch("lidco.cli.commands.arena_cmds.ArenaMode", return_value=mock_arena, create=True):
        result = run(arena_compare_handler("model-a model-b write hello world"))
    assert "Model" in result
    reset()


# ---- /arena leaderboard ----

def test_arena_leaderboard_no_votes(monkeypatch):
    reset()
    mock_lb = MagicMock()
    mock_lb.leaderboard.return_value = []
    acmds._leaderboard = mock_lb
    result = run(arena_leaderboard_handler())
    assert "No votes" in result
    reset()


def test_arena_leaderboard_with_votes(monkeypatch):
    reset()
    stat = MagicMock()
    stat.model = "gpt-4o"
    stat.wins = 5
    stat.appearances = 8
    stat.win_rate = 0.625
    mock_lb = MagicMock()
    mock_lb.leaderboard.return_value = [stat]
    acmds._leaderboard = mock_lb
    result = run(arena_leaderboard_handler())
    assert "gpt-4o" in result
    reset()


# ---- /arena vote ----

def test_arena_vote_no_args():
    result = run(arena_vote_handler(""))
    assert "Usage" in result


def test_arena_vote_no_active_comparison():
    reset()
    result = run(arena_vote_handler("model-a"))
    assert "No arena comparison" in result


def test_arena_vote_model_not_in_last_result(monkeypatch):
    reset()
    mock_entry = MagicMock()
    mock_entry.model = "model-a"
    mock_result = MagicMock()
    mock_result.entries = [mock_entry]
    mock_result.task = "t"
    acmds._last_arena_result = (MagicMock(), mock_result)
    mock_lb = MagicMock()
    acmds._leaderboard = mock_lb
    result = run(arena_vote_handler("unknown-model"))
    assert "not in last comparison" in result
    reset()


# ---- registration ----

def test_register_arena_commands():
    registry = MagicMock()
    register_arena_commands(registry)
    assert registry.register.call_count == 3
