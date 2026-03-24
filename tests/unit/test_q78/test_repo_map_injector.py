"""Tests for RepoMapInjector (T514)."""
import pytest
from unittest.mock import MagicMock

from lidco.context.repo_map_injector import RepoMapInjector


def _make_repo_map(output="map content"):
    m = MagicMock()
    m.generate.return_value = output
    return m


def test_inject_prepends_to_existing_system_message():
    injector = RepoMapInjector(_make_repo_map("REPOMAP"))
    messages = [
        {"role": "system", "content": "original system"},
        {"role": "user", "content": "hello"},
    ]
    result = injector.inject(messages)
    assert result[0]["role"] == "system"
    assert "REPOMAP" in result[0]["content"]
    assert "original system" in result[0]["content"]


def test_inject_inserts_system_message_if_absent():
    injector = RepoMapInjector(_make_repo_map("MAP"))
    messages = [{"role": "user", "content": "hi"}]
    result = injector.inject(messages)
    assert result[0]["role"] == "system"
    assert "MAP" in result[0]["content"]
    assert result[1]["role"] == "user"


def test_inject_disabled_returns_messages_unchanged():
    injector = RepoMapInjector(_make_repo_map("MAP"), enabled=False)
    messages = [{"role": "user", "content": "hi"}]
    result = injector.inject(messages)
    assert result is messages


def test_inject_returns_new_list():
    injector = RepoMapInjector(_make_repo_map("MAP"))
    messages = [{"role": "user", "content": "hi"}]
    result = injector.inject(messages)
    assert result is not messages


def test_inject_empty_block_still_injects_header():
    # Even with empty map content, build_context_block returns a non-empty header
    injector = RepoMapInjector(_make_repo_map(""))
    messages = [{"role": "user", "content": "hi"}]
    result = injector.inject(messages)
    assert result[0]["role"] == "system"
    assert "Repository Context" in result[0]["content"]


def test_toggle_flips_enabled():
    injector = RepoMapInjector(_make_repo_map("X"))
    assert injector.enabled is True
    state = injector.toggle()
    assert state is False
    assert injector.enabled is False
    state2 = injector.toggle()
    assert state2 is True


def test_build_context_block_without_seeder():
    injector = RepoMapInjector(_make_repo_map("RMAP"))
    block = injector.build_context_block()
    assert "## Repository Context" in block
    assert "RMAP" in block
    assert "## Memory" not in block


def test_build_context_block_with_seeder():
    seeder = MagicMock()
    seed = MagicMock()
    seed.prompt_block = "my memories"
    seeder.seed.return_value = seed

    injector = RepoMapInjector(_make_repo_map("RMAP"), session_seeder=seeder)
    block = injector.build_context_block()
    assert "## Repository Context" in block
    assert "## Memory" in block
    assert "my memories" in block


def test_estimate_tokens():
    injector = RepoMapInjector(_make_repo_map())
    assert injector.estimate_tokens("1234") == 1  # 4 chars / 4 = 1


def test_inject_repo_map_raises_handled_gracefully():
    bad_map = MagicMock()
    bad_map.generate.side_effect = RuntimeError("boom")
    injector = RepoMapInjector(bad_map)
    messages = [{"role": "user", "content": "hi"}]
    # Exception in generate() is caught; block still contains header
    result = injector.inject(messages)
    # Should not raise; result has a system message injected
    assert isinstance(result, list)
