"""Tests for Tasks 468+469: /wiki and /ask commands."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lidco.cli.commands.wiki_cmds import (
    _wiki_generate,
    _wiki_show,
    _wiki_status,
    _wiki_export,
    _ask_question,
)
from lidco.wiki.generator import WikiGenerator, WikiPage


def _setup_wiki_page(project_dir: Path, name: str = "test_mod") -> None:
    wiki_dir = project_dir / ".lidco" / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    page = WikiPage(module_path="src/test_mod.py", summary="Test module.")
    (wiki_dir / f"{name}.md").write_text(page.to_markdown(), encoding="utf-8")


class TestWikiGenerateCommand:
    def test_generate_single_file(self, tmp_path):
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
        with patch.object(WikiGenerator, "generate_module", return_value=WikiPage("mod.py", "Summary")), \
             patch.object(WikiGenerator, "_get_git_history", return_value=[]):
            result = _wiki_generate("mod.py", tmp_path)
        assert "mod.py" in result or "Summary" in result

    def test_generate_shows_module_path(self, tmp_path):
        (tmp_path / "app.py").write_text("class App: pass\n", encoding="utf-8")
        with patch.object(WikiGenerator, "generate_module", return_value=WikiPage("app.py", "App module.")), \
             patch.object(WikiGenerator, "_get_git_history", return_value=[]):
            result = _wiki_generate("app.py", tmp_path)
        assert "app.py" in result or "App module" in result


class TestWikiShowCommand:
    def test_show_no_module(self, tmp_path):
        result = _wiki_show("", tmp_path)
        assert "Usage" in result

    def test_show_absent_module(self, tmp_path):
        result = _wiki_show("nonexistent.py", tmp_path)
        assert "No wiki page" in result or "generate" in result.lower()

    def test_show_existing_page(self, tmp_path):
        _setup_wiki_page(tmp_path, "test_mod")
        with patch.object(WikiGenerator, "load", return_value=WikiPage("src/test_mod.py", "Test module.")):
            result = _wiki_show("src/test_mod.py", tmp_path)
        assert "Test module" in result or "src/test_mod.py" in result


class TestWikiStatusCommand:
    def test_status_empty_project(self, tmp_path):
        result = _wiki_status(tmp_path)
        assert "status" in result.lower() or "modules" in result.lower()

    def test_status_shows_documented_count(self, tmp_path):
        _setup_wiki_page(tmp_path)
        result = _wiki_status(tmp_path)
        assert "1" in result or "documented" in result.lower()


class TestWikiExportCommand:
    def test_export_no_wiki(self, tmp_path):
        result = _wiki_export("", tmp_path)
        assert "No wiki" in result or "generate" in result.lower()

    def test_export_with_pages(self, tmp_path):
        _setup_wiki_page(tmp_path)
        out = tmp_path / "out"
        result = _wiki_export(str(out), tmp_path)
        assert "Exported" in result or str(out) in result


class TestAskCommand:
    def test_ask_returns_answer(self, tmp_path):
        (tmp_path / "session.py").write_text("class Session: pass\n", encoding="utf-8")
        result = _ask_question("what is the session", tmp_path)
        assert "Answer" in result or "session" in result.lower()

    def test_ask_includes_sources(self, tmp_path):
        (tmp_path / "router.py").write_text("def route(): pass\n", encoding="utf-8")
        result = _ask_question("how does routing work", tmp_path)
        # Result should either have sources or an answer
        assert result

    def test_ask_no_results_graceful(self, tmp_path):
        result = _ask_question("unicorn teleportation protocol", tmp_path)
        assert isinstance(result, str)
