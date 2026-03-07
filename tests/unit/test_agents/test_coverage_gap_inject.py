"""Tests for coverage gap injection into the debugger agent context (graph.py)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.graph import GraphOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coverage_json(files: dict) -> dict:
    return {"files": files, "meta": {"version": "7.0"}}


def _make_orchestrator() -> GraphOrchestrator:
    """Build a minimal GraphOrchestrator with no-op LLM."""
    llm = MagicMock()
    registry = MagicMock()
    registry.list_agents.return_value = []
    registry.list_names.return_value = []
    return GraphOrchestrator(
        llm=llm,
        agent_registry=registry,
        project_dir=Path("."),
    )


# ---------------------------------------------------------------------------
# set_coverage_gap_inject
# ---------------------------------------------------------------------------


class TestSetCoverageGapInject:
    def test_default_enabled(self):
        orch = _make_orchestrator()
        assert orch._coverage_gap_inject_enabled is True

    def test_can_disable(self):
        orch = _make_orchestrator()
        orch.set_coverage_gap_inject(False)
        assert orch._coverage_gap_inject_enabled is False

    def test_can_re_enable(self):
        orch = _make_orchestrator()
        orch.set_coverage_gap_inject(False)
        orch.set_coverage_gap_inject(True)
        assert orch._coverage_gap_inject_enabled is True


# ---------------------------------------------------------------------------
# _build_coverage_gap_hint
# ---------------------------------------------------------------------------


class TestBuildCoverageGapHint:
    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path
        orch.set_coverage_gap_inject(False)

        result = await orch._build_coverage_gap_hint("File src/foo.py line 10")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_coverage_file(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path

        result = await orch._build_coverage_gap_hint("File src/foo.py line 10")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_file_in_error(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({"src/foo.py": {
            "executed_lines": [1, 2], "missing_lines": [3, 4],
            "excluded_lines": [], "missing_branches": [],
            "summary": {"percent_covered": 50.0},
        }})
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await orch._build_coverage_gap_hint("no file path here")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_gap_section_for_matching_file(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({"src/lidco/core/session.py": {
            "executed_lines": [1, 2],
            "missing_lines": [10, 11, 12],
            "excluded_lines": [],
            "missing_branches": [],
            "summary": {"percent_covered": 40.0},
        }})
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        error_ctx = 'File "src/lidco/core/session.py", line 10, in some_func'
        result = await orch._build_coverage_gap_hint(error_ctx)

        assert "session.py" in result
        assert "10" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_file_fully_covered(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        data = _make_coverage_json({"src/foo.py": {
            "executed_lines": [1, 2, 3],
            "missing_lines": [],
            "excluded_lines": [],
            "missing_branches": [],
            "summary": {"percent_covered": 100.0},
        }})
        (lidco_dir / "coverage.json").write_text(json.dumps(data), encoding="utf-8")

        result = await orch._build_coverage_gap_hint("File src/foo.py line 1")
        assert result == ""

    @pytest.mark.asyncio
    async def test_fail_silently_on_bad_json(self, tmp_path):
        orch = _make_orchestrator()
        orch._project_dir = tmp_path
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        (lidco_dir / "coverage.json").write_text("not json!", encoding="utf-8")

        result = await orch._build_coverage_gap_hint("File src/foo.py line 1")
        assert result == ""


# ---------------------------------------------------------------------------
# config integration — coverage_gap_inject in AgentsConfig
# ---------------------------------------------------------------------------


class TestCoverageGapConfig:
    def test_config_default(self):
        from lidco.core.config import AgentsConfig
        cfg = AgentsConfig()
        assert cfg.coverage_gap_inject is True

    def test_config_can_be_disabled(self):
        from lidco.core.config import AgentsConfig
        cfg = AgentsConfig(coverage_gap_inject=False)
        assert cfg.coverage_gap_inject is False
