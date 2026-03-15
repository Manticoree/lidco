"""Tests for Task 381 — /commit with template support."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_registry(llm_content="feat: add new feature"):
    from lidco.cli.commands import CommandRegistry

    registry = CommandRegistry()
    session = MagicMock()
    llm_resp = MagicMock()
    llm_resp.content = llm_content
    session.llm.complete = AsyncMock(return_value=llm_resp)
    registry.set_session(session)
    return registry


def _invoke(handler, arg: str = "") -> str:
    return asyncio.run(handler(arg=arg))


class TestCommitTemplate:
    def test_commit_still_registered(self):
        """The /commit command should still exist after Q56 enhancement."""
        reg = _make_registry()
        cmd = reg.get("commit")
        assert cmd is not None
        assert cmd.name == "commit"

    def test_commit_no_session(self):
        from lidco.cli.commands import CommandRegistry
        reg = CommandRegistry()
        reg._session = None
        cmd = reg.get("commit")
        result = _invoke(cmd.handler, "")
        assert "session" in result.lower() or "initialized" in result.lower()

    def test_commit_no_changes(self):
        reg = _make_registry()
        cmd = reg.get("commit")

        def _fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=_fake_run):
            result = _invoke(cmd.handler, "")

        assert "no changes" in result.lower() or "stage" in result.lower()

    def test_commit_template_loaded_when_present(self, tmp_path: Path, monkeypatch):
        """When .lidco/commit-template.md exists, it should be injected into LLM prompt."""
        # Create template file
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        template_file = lidco_dir / "commit-template.md"
        template_file.write_text("type(scope): short description\n\nbody", encoding="utf-8")

        reg = _make_registry("feat(cli): add template support")

        captured_prompts: list[str] = []

        async def _fake_complete(messages, **kwargs):
            for msg in messages:
                captured_prompts.append(msg.content)
            resp = MagicMock()
            resp.content = "feat(cli): add template support"
            return resp

        reg._session.llm.complete = _fake_complete

        def _fake_run(args, **kwargs):
            m = MagicMock()
            if "diff" in args:
                m.returncode = 0
                m.stdout = "diff --git a/foo.py\n+x = 1"
                m.stderr = ""
            else:
                m.returncode = 0
                m.stdout = ""
                m.stderr = ""
            return m

        monkeypatch.chdir(tmp_path)
        with patch("subprocess.run", side_effect=_fake_run):
            # Mock the prompt to cancel
            with patch("rich.prompt.Prompt.ask", return_value="n"):
                result = _invoke(reg.get("commit").handler, "")

        # The template content should have been injected in the LLM prompt
        assert any("type(scope)" in p for p in captured_prompts)

    def test_commit_template_missing_proceeds_normally(self, tmp_path: Path, monkeypatch):
        """When no template exists, /commit should still work normally."""
        monkeypatch.chdir(tmp_path)
        reg = _make_registry("chore: cleanup")

        def _fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "diff --git a/foo.py\n+y = 2" if "diff" in args else ""
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=_fake_run):
            with patch("rich.prompt.Prompt.ask", return_value="n"):
                result = _invoke(reg.get("commit").handler, "")

        assert "cancelled" in result.lower() or "commit" in result.lower()

    def test_commit_with_explicit_message_skips_llm(self, tmp_path: Path, monkeypatch):
        """If user provides message arg, LLM should not be called."""
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        called = [False]

        async def _fake_complete(messages, **kwargs):
            called[0] = True
            resp = MagicMock()
            resp.content = "should not be called"
            return resp

        reg._session.llm.complete = _fake_complete

        def _fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "diff content" if "diff" in args else ""
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=_fake_run):
            with patch("rich.prompt.Prompt.ask", return_value="n"):
                result = _invoke(reg.get("commit").handler, "fix: manual message")

        assert not called[0], "LLM should not be called when message is provided"
        assert "cancelled" in result.lower() or "commit" in result.lower()
