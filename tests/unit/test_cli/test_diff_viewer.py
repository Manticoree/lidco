"""Tests for diff_viewer — syntax-highlighted git diff panel."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from lidco.cli.diff_viewer import get_git_diff, show_git_diff


@pytest.fixture()
def console_and_buf():
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=100)
    return console, buf


_SAMPLE_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc1234..def5678 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,4 @@
 import os
+import sys
 def main():
-    pass
+    sys.exit(0)
"""


class TestGetGitDiff:
    def test_returns_stdout_on_success(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=_SAMPLE_DIFF, returncode=0)
            result = get_git_diff(tmp_path)
        assert "import sys" in result

    def test_returns_empty_string_when_no_changes(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            result = get_git_diff(tmp_path)
        assert result == ""

    def test_returns_empty_string_when_git_not_found(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_git_diff(tmp_path)
        assert result == ""

    def test_returns_empty_string_on_timeout(self, tmp_path: Path) -> None:
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            result = get_git_diff(tmp_path)
        assert result == ""

    def test_returns_empty_string_on_oserror(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=OSError):
            result = get_git_diff(tmp_path)
        assert result == ""

    def test_uses_project_dir_as_cwd(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            get_git_diff(tmp_path)
        call_kwargs = mock_run.call_args
        assert str(tmp_path) == call_kwargs.kwargs.get("cwd") or str(tmp_path) == call_kwargs[1].get("cwd")

    def test_uses_cwd_when_no_project_dir(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            get_git_diff(None)
        assert mock_run.called


class TestShowGitDiff:
    def test_no_diff_produces_no_output(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        assert buf.getvalue() == ""

    def test_git_not_found_produces_no_output(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run", side_effect=FileNotFoundError):
            show_git_diff(console, project_dir=tmp_path)
        assert buf.getvalue() == ""

    def test_diff_panel_shown_for_non_empty_diff(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=_SAMPLE_DIFF, returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        output = buf.getvalue()
        assert "Changes" in output

    def test_diff_panel_contains_diff_content(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=_SAMPLE_DIFF, returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        output = buf.getvalue()
        # Panel content should include some part of the diff
        assert "foo.py" in output or "import" in output or "@@" in output

    def test_short_diff_not_truncated(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=_SAMPLE_DIFF, returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        assert "hidden" not in buf.getvalue()

    def test_long_diff_is_truncated(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        many_lines = "\n".join([f"+line_{i}" for i in range(200)])
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=many_lines, returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        assert "hidden" in buf.getvalue()

    def test_truncation_message_shows_hidden_count(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        # 100 lines over the 80-line limit → 20 hidden
        lines_101 = "\n".join([f"+line_{i}" for i in range(100)])
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=lines_101, returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        output = buf.getvalue()
        assert "20 hidden" in output

    def test_whitespace_only_diff_produces_no_output(
        self, tmp_path: Path, console_and_buf: tuple
    ) -> None:
        console, buf = console_and_buf
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="   \n  \n", returncode=0)
            show_git_diff(console, project_dir=tmp_path)
        assert buf.getvalue() == ""
