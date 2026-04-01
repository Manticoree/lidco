"""Tests for slash commands — /export and /import."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _make_session(
    *,
    history: list[dict[str, str]] | None = None,
    model: str = "openai/glm-4.7",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
):
    """Build a minimal fake session for command tests."""
    orchestrator = MagicMock()
    orchestrator._conversation_history = history if history is not None else []
    config = SimpleNamespace(llm=SimpleNamespace(default_model=model))
    token_budget = SimpleNamespace(
        total_prompt_tokens=prompt_tokens,
        total_completion_tokens=completion_tokens,
        total_cost_usd=cost_usd,
    )
    return SimpleNamespace(
        orchestrator=orchestrator, config=config, token_budget=token_budget
    )


# ---------------------------------------------------------------------------
# /export — shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def registry():
    return CommandRegistry()


HISTORY_2 = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
]

HISTORY_4 = [
    {"role": "user", "content": "q1"},
    {"role": "assistant", "content": "a1"},
    {"role": "user", "content": "q2"},
    {"role": "assistant", "content": "a2"},
]


# ---------------------------------------------------------------------------
# /export — error cases
# ---------------------------------------------------------------------------

class TestExportErrors:
    def test_no_session(self, registry: CommandRegistry) -> None:
        handler = registry.get("export").handler
        import asyncio, inspect
        if inspect.iscoroutinefunction(handler):
            result = asyncio.run(handler(""))
        else:
            result = handler("")
        assert isinstance(result, str)

    def test_empty_history(self, registry: CommandRegistry) -> None:
        registry.set_session(_make_session(history=[]))
        handler = registry.get("export").handler
        import asyncio, inspect
        if inspect.iscoroutinefunction(handler):
            result = asyncio.run(handler(""))
        else:
            result = handler("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# /export — JSON (default)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Q92 overrides /export with sync handler — tested in test_q92/")
class TestExportJson:
    @pytest.mark.asyncio
    async def test_default_creates_json_in_lidco_exports(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_2, model="openai/glm-4.7"))

        result = registry.get("export").handler("")

        assert "2 messages" in result
        assert "Session exported to" in result

        json_files = list((tmp_path / ".lidco" / "exports").glob("session-*.json"))
        assert len(json_files) == 1

    @pytest.mark.asyncio
    async def test_json_structure(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(
            _make_session(
                history=HISTORY_2,
                model="openai/glm-4.7",
                prompt_tokens=1200,
                completion_tokens=300,
                cost_usd=0.003,
            )
        )

        registry.get("export").handler("")

        json_files = list((tmp_path / ".lidco" / "exports").glob("*.json"))
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert data["model"] == "openai/glm-4.7"
        assert "exported_at" in data
        assert "project_dir" in data
        assert "lidco_version" in data
        assert data["messages"] == HISTORY_2
        assert data["tokens"]["prompt"] == 1200
        assert data["tokens"]["completion"] == 300
        assert data["tokens"]["total"] == 1500
        assert abs(data["cost_usd"] - 0.003) < 1e-6

    @pytest.mark.asyncio
    async def test_custom_json_path(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_2))

        custom = tmp_path / "my-export.json"
        result = registry.get("export").handler(str(custom))

        assert custom.exists()
        assert "2 messages" in result
        data = json.loads(custom.read_text(encoding="utf-8"))
        assert len(data["messages"]) == 2

    @pytest.mark.asyncio
    async def test_json_messages_contain_all_turns(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_4))

        registry.get("export").handler("")

        files = list((tmp_path / ".lidco" / "exports").glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert len(data["messages"]) == 4
        roles = [m["role"] for m in data["messages"]]
        assert roles == ["user", "assistant", "user", "assistant"]


# ---------------------------------------------------------------------------
# /export --md (Markdown format)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Q92 overrides /export with sync handler — tested in test_q92/")
class TestExportMarkdown:
    @pytest.mark.asyncio
    async def test_md_flag_creates_markdown(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_2, model="openai/glm-4.7"))

        result = registry.get("export").handler("--md")

        assert "2 messages" in result
        md_files = list(tmp_path.glob("lidco-session-*.md"))
        assert len(md_files) == 1

    @pytest.mark.asyncio
    async def test_md_content(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_2, model="openai/glm-4.7"))

        registry.get("export").handler("--md")

        md_files = list(tmp_path.glob("lidco-session-*.md"))
        content = md_files[0].read_text(encoding="utf-8")

        assert "# LIDCO Session Export" in content
        assert "**Date:**" in content
        assert "**Model:** openai/glm-4.7" in content
        assert "**Directory:**" in content
        assert "## You" in content
        assert "Hello" in content
        assert "## LIDCO" in content
        assert "Hi there!" in content

    @pytest.mark.asyncio
    async def test_md_custom_path(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_2))

        custom = tmp_path / "custom.md"
        registry.get("export").handler(f"--md {custom}")

        assert custom.exists()
        content = custom.read_text(encoding="utf-8")
        assert "# LIDCO Session Export" in content

    @pytest.mark.asyncio
    async def test_md_role_headers_alternate(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(_make_session(history=HISTORY_4))

        registry.get("export").handler("--md")

        md_files = list(tmp_path.glob("lidco-session-*.md"))
        content = md_files[0].read_text(encoding="utf-8")

        lines = content.splitlines()
        you_positions = [i for i, line in enumerate(lines) if line.strip() == "## You"]
        lidco_positions = [i for i, line in enumerate(lines) if line.strip() == "## LIDCO"]

        assert len(you_positions) == 2
        assert len(lidco_positions) == 2
        assert you_positions[0] < lidco_positions[0]
        assert you_positions[1] < lidco_positions[1]

    @pytest.mark.asyncio
    async def test_md_token_metadata(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        registry.set_session(
            _make_session(
                history=HISTORY_2,
                prompt_tokens=5000,
                completion_tokens=1000,
                cost_usd=0.005,
            )
        )

        registry.get("export").handler("--md")

        md_files = list(tmp_path.glob("lidco-session-*.md"))
        content = md_files[0].read_text(encoding="utf-8")

        assert "**Tokens:**" in content
        assert "**Cost:**" in content


# ---------------------------------------------------------------------------
# /import
# ---------------------------------------------------------------------------

class TestImportHandler:
    @pytest.mark.asyncio
    async def test_no_session(self, registry: CommandRegistry) -> None:
        result = await registry.get("import").handler(arg="file.json")
        assert result == "Session not initialized."

    @pytest.mark.asyncio
    async def test_no_arg_shows_usage(self, registry: CommandRegistry) -> None:
        registry.set_session(_make_session())
        result = await registry.get("import").handler()
        assert "Usage" in result or "/import" in result

    @pytest.mark.asyncio
    async def test_file_not_found(
        self, registry: CommandRegistry, tmp_path: Path
    ) -> None:
        registry.set_session(_make_session())
        result = await registry.get("import").handler(arg=str(tmp_path / "nope.json"))
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_import_restores_history(
        self, registry: CommandRegistry, tmp_path: Path
    ) -> None:
        export_data = {
            "lidco_version": "0.1.0",
            "exported_at": "2025-01-15T10:30:00",
            "model": "openai/glm-4.7",
            "project_dir": "/some/project",
            "tokens": {"prompt": 1000, "completion": 200, "total": 1200},
            "cost_usd": 0.002,
            "messages": HISTORY_2,
        }
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(export_data), encoding="utf-8")

        session = _make_session()
        registry.set_session(session)

        result = await registry.get("import").handler(arg=str(export_file))

        assert "2 messages" in result
        assert "openai/glm-4.7" in result
        # Verify restore_history was called with the messages
        session.orchestrator.restore_history.assert_called_once_with(HISTORY_2)

    @pytest.mark.asyncio
    async def test_import_summary_contains_metadata(
        self, registry: CommandRegistry, tmp_path: Path
    ) -> None:
        export_data = {
            "exported_at": "2025-01-15T10:30:00",
            "model": "openai/glm-4.7",
            "tokens": {"total": 5000},
            "messages": HISTORY_4,
        }
        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(export_data), encoding="utf-8")

        registry.set_session(_make_session())
        result = await registry.get("import").handler(arg=str(export_file))

        assert "4 messages" in result
        assert "openai/glm-4.7" in result
        assert "5,000" in result or "5000" in result

    @pytest.mark.asyncio
    async def test_import_invalid_json(
        self, registry: CommandRegistry, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")

        registry.set_session(_make_session())
        result = await registry.get("import").handler(arg=str(bad_file))
        assert "failed" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_import_missing_messages_key(
        self, registry: CommandRegistry, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(json.dumps({"model": "openai/glm-4.7"}), encoding="utf-8")

        registry.set_session(_make_session())
        result = await registry.get("import").handler(arg=str(bad_file))
        assert "messages" in result.lower() or "invalid" in result.lower()

    @pytest.mark.skip(reason="Q92 overrides /export — tested in test_q92/")
    @pytest.mark.asyncio
    async def test_roundtrip_export_then_import(
        self, registry: CommandRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Export a session to JSON, then import it back."""
        monkeypatch.chdir(tmp_path)
        session = _make_session(history=HISTORY_4)
        registry.set_session(session)

        # Export
        registry.get("export").handler("")
        json_files = list((tmp_path / ".lidco" / "exports").glob("*.json"))
        assert len(json_files) == 1

        # Import
        result = await registry.get("import").handler(arg=str(json_files[0]))
        assert "4 messages" in result
        session.orchestrator.restore_history.assert_called_once_with(HISTORY_4)
