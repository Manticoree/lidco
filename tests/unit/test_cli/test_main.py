"""Tests for lidco.__main__ — CLI entry point dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── main() dispatch ───────────────────────────────────────────────────────────


class TestMainDispatch:
    def test_serve_dispatches_to_run_serve(self) -> None:
        with patch("lidco.__main__._run_serve") as mock_serve:
            with patch("sys.argv", ["lidco", "serve"]):
                from lidco.__main__ import main
                main()
            mock_serve.assert_called_once_with([])

    def test_serve_with_flags_passes_remaining_args(self) -> None:
        with patch("lidco.__main__._run_serve") as mock_serve:
            with patch("sys.argv", ["lidco", "serve", "--port", "9000"]):
                from lidco.__main__ import main
                main()
            mock_serve.assert_called_once_with(["--port", "9000"])

    def test_index_dispatches_to_run_index(self) -> None:
        with patch("lidco.__main__._run_index") as mock_index:
            with patch("sys.argv", ["lidco", "index"]):
                from lidco.__main__ import main
                main()
            mock_index.assert_called_once_with([])

    def test_index_with_flags_passes_remaining_args(self) -> None:
        with patch("lidco.__main__._run_index") as mock_index:
            with patch("sys.argv", ["lidco", "index", "--incremental"]):
                from lidco.__main__ import main
                main()
            mock_index.assert_called_once_with(["--incremental"])

    def test_no_args_dispatches_to_run_cli(self) -> None:
        with patch("lidco.cli.app.run_cli") as mock_cli:
            with patch("sys.argv", ["lidco"]):
                from lidco.__main__ import main
                main()
            mock_cli.assert_called_once()

    def test_unknown_subcommand_dispatches_to_run_cli(self) -> None:
        # Anything not "serve" or "index" falls through to REPL
        with patch("lidco.cli.app.run_cli") as mock_cli:
            with patch("sys.argv", ["lidco", "repl"]):
                from lidco.__main__ import main
                main()
            mock_cli.assert_called_once()


# ── _run_serve ────────────────────────────────────────────────────────────────


class TestRunServe:
    def test_default_host_and_port(self) -> None:
        with patch("lidco.server.app.run_server") as mock_run:
            from lidco.__main__ import _run_serve
            _run_serve([])
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8321, project_dir=None
            )

    def test_custom_port(self) -> None:
        with patch("lidco.server.app.run_server") as mock_run:
            from lidco.__main__ import _run_serve
            _run_serve(["--port", "9000"])
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=9000, project_dir=None
            )

    def test_custom_host(self) -> None:
        with patch("lidco.server.app.run_server") as mock_run:
            from lidco.__main__ import _run_serve
            _run_serve(["--host", "0.0.0.0"])
            mock_run.assert_called_once_with(
                host="0.0.0.0", port=8321, project_dir=None
            )

    def test_project_dir_flag(self, tmp_path: Path) -> None:
        with patch("lidco.server.app.run_server") as mock_run:
            from lidco.__main__ import _run_serve
            _run_serve(["--project-dir", str(tmp_path)])
            mock_run.assert_called_once_with(
                host="127.0.0.1", port=8321, project_dir=tmp_path
            )

    def test_unknown_flag_exits(self) -> None:
        from lidco.__main__ import _run_serve
        with pytest.raises(SystemExit):
            _run_serve(["--unknown"])


# ── _run_index incremental path ───────────────────────────────────────────────


class TestRunIndexIncremental:
    def test_incremental_after_full_uses_incremental(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")

        from lidco.__main__ import _run_index

        # First run: full index
        _run_index(["--dir", str(tmp_path)])
        capsys.readouterr()

        # Second run: incremental (DB already has files)
        _run_index(["--dir", str(tmp_path), "--incremental"])
        captured = capsys.readouterr()
        assert "incremental" in captured.out

    def test_incremental_on_empty_index_falls_back_to_full(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")

        from lidco.__main__ import _run_index

        # First run with --incremental but no existing index → should fall back to full
        _run_index(["--dir", str(tmp_path), "--incremental"])
        captured = capsys.readouterr()
        assert "full" in captured.out
