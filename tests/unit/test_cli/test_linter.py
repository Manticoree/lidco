"""Tests for post-edit linting integration."""

from __future__ import annotations

import subprocess
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from lidco.cli.linter import _run_ruff, show_lint_results


class TestRunRuff:
    def test_returns_empty_when_ruff_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _run_ruff(["any.py"]) == ""

    def test_returns_empty_on_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 15)):
            assert _run_ruff(["any.py"]) == ""

    def test_returns_stdout_on_success(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="file.py:1:1: E302 ...\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            output = _run_ruff(["file.py"])
        assert "E302" in output

    def test_returns_empty_when_no_issues(self) -> None:
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            assert _run_ruff(["clean.py"]) == ""


class TestShowLintResults:
    def _console(self) -> tuple[Console, StringIO]:
        buf = StringIO()
        c = Console(file=buf, force_terminal=False, width=120)
        return c, buf

    def test_no_output_for_non_python_files(self) -> None:
        console, buf = self._console()
        with patch("lidco.cli.linter._run_ruff") as mock_ruff:
            show_lint_results(console, ["script.sh", "README.md"])
        mock_ruff.assert_not_called()
        assert buf.getvalue() == ""

    def test_shows_panel_when_issues_found(self) -> None:
        console, buf = self._console()
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="app.py:5:1: F401 unused import\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            show_lint_results(console, ["app.py"])
        output = buf.getvalue()
        assert "F401" in output
        assert "Lint" in output

    def test_no_panel_when_clean(self) -> None:
        console, buf = self._console()
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            show_lint_results(console, ["clean.py"])
        assert buf.getvalue() == ""

    def test_truncates_many_issues(self) -> None:
        console, buf = self._console()
        many_issues = "\n".join(f"file.py:{i}:1: E302 issue" for i in range(60))
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=many_issues, stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            show_lint_results(console, ["file.py"])
        output = buf.getvalue()
        assert "more issues" in output

    def test_filters_only_python_files(self) -> None:
        """Only .py files are passed to ruff."""
        console, buf = self._console()
        captured_paths: list[list[str]] = []

        def mock_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess:
            captured_paths.append(cmd)
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=mock_run):
            show_lint_results(console, ["app.py", "styles.css", "utils.py"])

        if captured_paths:
            called_paths = captured_paths[0]
            assert "styles.css" not in called_paths
            assert "app.py" in called_paths
            assert "utils.py" in called_paths


class TestSecurityAgent:
    """Smoke test that the security agent can be created."""

    def test_security_agent_creation(self) -> None:
        from unittest.mock import MagicMock
        from lidco.agents.builtin.security import create_security_agent

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        agent = create_security_agent(mock_llm, mock_registry)
        assert agent.name == "security"
        assert "OWASP" in agent.get_system_prompt()

    def test_security_agent_uses_readonly_tools(self) -> None:
        from unittest.mock import MagicMock
        from lidco.agents.builtin.security import create_security_agent

        agent = create_security_agent(MagicMock(), MagicMock())
        assert {"file_read", "glob", "grep"}.issubset(set(agent.config.tools))
        assert "web_search" in agent.config.tools
        assert "web_fetch" in agent.config.tools

    def test_security_agent_cannot_write(self) -> None:
        from unittest.mock import MagicMock
        from lidco.agents.builtin.security import create_security_agent

        agent = create_security_agent(MagicMock(), MagicMock())
        assert "file_write" not in agent.config.tools
        assert "file_edit" not in agent.config.tools
        assert "bash" not in agent.config.tools

    def test_security_agent_in_session(self) -> None:
        from unittest.mock import MagicMock, patch
        from lidco.core.config import LidcoConfig

        with (
            patch("lidco.core.session.LiteLLMProvider"),
            patch("lidco.core.session.ModelRouter"),
            patch("lidco.core.session.ToolRegistry") as mock_reg,
        ):
            mock_reg.create_default_registry.return_value = MagicMock()
            from lidco.core.session import Session
            session = Session(config=LidcoConfig())

        agent_names = session.agent_registry.list_names()
        assert "security" in agent_names
