"""Tests for slash commands — /export."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _make_session(*, history: list[dict[str, str]] | None = None, model: str = "gpt-4o"):
    """Build a minimal fake session for command tests."""
    orchestrator = MagicMock()
    orchestrator._conversation_history = history if history is not None else []
    config = SimpleNamespace(llm=SimpleNamespace(default_model=model))
    return SimpleNamespace(orchestrator=orchestrator, config=config)


class TestExportHandler:
    """Tests for the /export slash command."""

    @pytest.fixture
    def registry(self):
        return CommandRegistry()

    @pytest.mark.asyncio
    async def test_no_session(self, registry):
        cmd = registry.get("export")
        assert cmd is not None
        result = await cmd.handler()
        assert result == "Session not initialized."

    @pytest.mark.asyncio
    async def test_empty_history(self, registry):
        registry.set_session(_make_session(history=[]))
        result = await registry.get("export").handler()
        assert result == "No conversation to export."

    @pytest.mark.asyncio
    async def test_export_default_path(self, registry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        registry.set_session(_make_session(history=history, model="claude-sonnet-4-5-20250514"))
        result = await registry.get("export").handler()

        assert "2 messages" in result
        assert "Session exported to" in result

        # Find the created file
        md_files = list(tmp_path.glob("lidco-session-*.md"))
        assert len(md_files) == 1

        content = md_files[0].read_text(encoding="utf-8")
        assert "# LIDCO Session Export" in content
        assert "claude-sonnet-4-5-20250514" in content
        assert "## You" in content
        assert "Hello" in content
        assert "## LIDCO" in content
        assert "Hi there!" in content

    @pytest.mark.asyncio
    async def test_export_custom_path(self, registry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = [{"role": "user", "content": "test"}]
        registry.set_session(_make_session(history=history))

        custom = tmp_path / "my-export.md"
        result = await registry.get("export").handler(arg=str(custom))

        assert custom.exists()
        assert "1 messages" in result
        content = custom.read_text(encoding="utf-8")
        assert "# LIDCO Session Export" in content
        assert "## You" in content
        assert "test" in content

    @pytest.mark.asyncio
    async def test_metadata_present(self, registry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = [{"role": "user", "content": "x"}]
        registry.set_session(_make_session(history=history, model="gpt-4o"))
        await registry.get("export").handler()

        md_files = list(tmp_path.glob("lidco-session-*.md"))
        content = md_files[0].read_text(encoding="utf-8")

        assert "**Date:**" in content
        assert "**Model:** gpt-4o" in content
        assert "**Directory:**" in content
        assert "---" in content

    @pytest.mark.asyncio
    async def test_role_headers_alternate(self, registry, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        registry.set_session(_make_session(history=history))
        await registry.get("export").handler()

        md_files = list(tmp_path.glob("lidco-session-*.md"))
        content = md_files[0].read_text(encoding="utf-8")

        you_positions = [i for i, line in enumerate(content.splitlines()) if line.strip() == "## You"]
        lidco_positions = [i for i, line in enumerate(content.splitlines()) if line.strip() == "## LIDCO"]

        assert len(you_positions) == 2
        assert len(lidco_positions) == 2
        # Each "You" should come before the corresponding "LIDCO"
        assert you_positions[0] < lidco_positions[0]
        assert you_positions[1] < lidco_positions[1]
