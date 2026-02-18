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

    def test_unknown_subcommand_exits_with_error(self) -> None:
        # Unknown positional args (not --flags) are rejected with an error
        with patch("sys.argv", ["lidco", "repl"]):
            import pytest
            from lidco.__main__ import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


# ── _parse_repl_flags ─────────────────────────────────────────────────────────


class TestParseReplFlags:
    def test_no_flags_returns_defaults(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags([])
        assert f.no_review is False
        assert f.no_plan is False
        assert f.no_streaming is False
        assert f.agent is None
        assert f.model is None

    def test_no_review_flag(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--no-review"])
        assert f.no_review is True

    def test_no_plan_flag(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--no-plan"])
        assert f.no_plan is True

    def test_no_streaming_flag(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--no-streaming"])
        assert f.no_streaming is True

    def test_agent_flag(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--agent", "reviewer"])
        assert f.agent == "reviewer"

    def test_model_flag(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--model", "ollama/llama3.1"])
        assert f.model == "ollama/llama3.1"

    def test_combined_flags(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        f = _parse_repl_flags(["--no-review", "--no-plan", "--agent", "coder"])
        assert f.no_review is True
        assert f.no_plan is True
        assert f.agent == "coder"

    def test_unknown_flag_exits(self) -> None:
        from lidco.__main__ import _parse_repl_flags
        with pytest.raises(SystemExit) as exc_info:
            _parse_repl_flags(["--unknown"])
        assert exc_info.value.code == 1

    def test_help_flag_exits_zero(self) -> None:
        with patch("sys.argv", ["lidco", "--help"]):
            from lidco.__main__ import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_flags_passed_to_run_cli(self) -> None:
        with patch("lidco.cli.app.run_cli") as mock_cli:
            with patch("sys.argv", ["lidco", "--no-review", "--agent", "reviewer"]):
                from lidco.__main__ import main
                main()
        mock_cli.assert_called_once()
        flags = mock_cli.call_args.kwargs["flags"]
        assert flags.no_review is True
        assert flags.agent == "reviewer"


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
