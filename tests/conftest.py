"""Shared pytest fixtures and configuration for LIDCO test suite."""
from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Event loop isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_event_loop_policy():
    """Ensure each test gets a fresh event loop, preventing cross-test contamination.

    Without this, tests that use asyncio.get_event_loop() fail when run after
    tests that close the event loop (e.g., test_cli fixtures).
    """
    yield
    # After each test, reset any closed loops
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            asyncio.get_event_loop_policy().set_event_loop(asyncio.new_event_loop())
    except RuntimeError:
        asyncio.get_event_loop_policy().set_event_loop(asyncio.new_event_loop())


# ---------------------------------------------------------------------------
# Common mock factories
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """A minimal mock Session object for command handler tests."""
    session = MagicMock()
    session.config = MagicMock()
    session.config.agents = MagicMock()
    session.orchestrator = MagicMock()
    session.orchestrator.handle = AsyncMock(return_value=MagicMock(content="ok"))
    return session


@pytest.fixture
def mock_llm_response():
    """Factory for mock LLM responses."""
    def _make(content: str = "test response"):
        resp = MagicMock()
        resp.content = content
        resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        return resp
    return _make


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with basic structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run a coroutine synchronously. Prefer asyncio.run() in tests directly."""
    return asyncio.run(coro)
