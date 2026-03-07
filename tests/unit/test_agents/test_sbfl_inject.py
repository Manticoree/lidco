"""Tests for SBFL injection in GraphOrchestrator (_build_sbfl_hint, set_sbfl_inject)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.graph import GraphOrchestrator


def _make_orch(project_dir: Path) -> GraphOrchestrator:
    llm = MagicMock()
    registry = MagicMock()
    registry.list_agents.return_value = []
    orch = GraphOrchestrator(
        llm=llm,
        agent_registry=registry,
        project_dir=project_dir,
    )
    return orch


class TestSetSbflInject:
    def test_default_enabled(self, tmp_path):
        orch = _make_orch(tmp_path)
        assert orch._sbfl_inject_enabled is True

    def test_set_false(self, tmp_path):
        orch = _make_orch(tmp_path)
        orch.set_sbfl_inject(False)
        assert orch._sbfl_inject_enabled is False

    def test_set_true(self, tmp_path):
        orch = _make_orch(tmp_path)
        orch.set_sbfl_inject(False)
        orch.set_sbfl_inject(True)
        assert orch._sbfl_inject_enabled is True


class TestBuildSbflHint:
    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self, tmp_path):
        orch = _make_orch(tmp_path)
        orch.set_sbfl_inject(False)
        result = await orch._build_sbfl_hint("src/foo.py line 10 error")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_file_path(self, tmp_path):
        orch = _make_orch(tmp_path)
        result = await orch._build_sbfl_hint("some error with no path")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_coverage_file(self, tmp_path):
        orch = _make_orch(tmp_path)
        error_ctx = 'File "src/lidco/core/session.py", line 42, in run'
        result = await orch._build_sbfl_hint(error_ctx)
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_sbfl_section_when_data_available(self, tmp_path):
        (tmp_path / ".coverage").write_bytes(b"fake coverage file")
        orch = _make_orch(tmp_path)

        fake_spectra = {"test_foo": {10, 20}, "test_bar": {10}}
        fake_hint = "## Suspicious Lines (Ochiai)\n\n| Line | Score |"

        with patch("lidco.core.sbfl.read_coverage_contexts", return_value=fake_spectra), \
             patch("lidco.core.sbfl.format_suspicious_lines", return_value=fake_hint):
            error_ctx = 'File "src/lidco/core/errors.py", line 42, in run'
            result = await orch._build_sbfl_hint(error_ctx)

        assert "Suspicious Lines" in result

    @pytest.mark.asyncio
    async def test_fail_silent_on_exception(self, tmp_path):
        orch = _make_orch(tmp_path)
        with patch("lidco.core.sbfl.read_coverage_contexts", side_effect=RuntimeError("boom")):
            (tmp_path / ".coverage").write_bytes(b"x")
            error_ctx = 'File "src/foo.py", line 10, in fn'
            result = await orch._build_sbfl_hint(error_ctx)
        assert result == ""

    @pytest.mark.asyncio
    async def test_empty_spectra_returns_empty(self, tmp_path):
        (tmp_path / ".coverage").write_bytes(b"fake")
        orch = _make_orch(tmp_path)
        with patch("lidco.core.sbfl.read_coverage_contexts", return_value={}):
            error_ctx = 'File "src/lidco/core/foo.py", line 10, in run'
            result = await orch._build_sbfl_hint(error_ctx)
        assert result == ""
