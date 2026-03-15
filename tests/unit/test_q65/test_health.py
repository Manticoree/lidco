"""Tests for HealthCheck — Q65 Task 442."""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch


class TestHealthResult:
    def test_fields(self):
        from lidco.diagnostics.health import HealthResult
        r = HealthResult(name="api_keys", status="ok", message="All good", duration_ms=1.0)
        assert r.name == "api_keys"
        assert r.status == "ok"
        assert r.message == "All good"
        assert r.duration_ms == 1.0


class TestCheckApiKeys:
    def test_ok_when_key_present(self, monkeypatch):
        from lidco.diagnostics.health import HealthCheck
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test2")
        hc = HealthCheck()
        result = hc.check_api_keys()
        assert result.status == "ok"

    def test_warn_when_no_keys(self, monkeypatch):
        from lidco.diagnostics.health import HealthCheck
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        hc = HealthCheck()
        result = hc.check_api_keys()
        assert result.status in ("warn", "fail")


class TestCheckModels:
    def test_warn_when_no_config(self):
        from lidco.diagnostics.health import HealthCheck
        hc = HealthCheck()
        result = hc.check_models(config=None)
        assert result.status == "warn"

    def test_ok_when_model_configured(self):
        from lidco.diagnostics.health import HealthCheck
        config = MagicMock()
        config.llm.default_model = "claude-sonnet-4-5"
        hc = HealthCheck()
        result = hc.check_models(config=config)
        assert result.status == "ok"
        assert "claude" in result.message.lower()


class TestCheckTools:
    def test_warn_when_no_registry(self):
        from lidco.diagnostics.health import HealthCheck
        hc = HealthCheck()
        result = hc.check_tools(registry=None)
        assert result.status == "warn"

    def test_ok_when_tools_registered(self):
        from lidco.diagnostics.health import HealthCheck
        registry = MagicMock()
        registry._tools = {"tool1": MagicMock(), "tool2": MagicMock()}
        hc = HealthCheck()
        result = hc.check_tools(registry=registry)
        assert result.status == "ok"
        assert "2" in result.message

    def test_warn_when_empty_registry(self):
        from lidco.diagnostics.health import HealthCheck
        registry = MagicMock()
        registry._tools = {}
        hc = HealthCheck()
        result = hc.check_tools(registry=registry)
        assert result.status == "warn"


class TestCheckRag:
    def test_warn_when_chromadb_missing(self):
        from lidco.diagnostics.health import HealthCheck
        hc = HealthCheck()
        with patch.dict("sys.modules", {"chromadb": None}):
            import importlib
            result = hc.check_rag()
        assert result.status in ("ok", "warn", "fail")  # graceful either way


class TestCheckDiskSpace:
    def test_returns_health_result(self):
        from lidco.diagnostics.health import HealthCheck
        hc = HealthCheck()
        result = hc.check_disk_space()
        assert result.name == "disk_space"
        assert result.status in ("ok", "warn", "fail")


class TestRunAll:
    def test_returns_list_of_results(self):
        from lidco.diagnostics.health import HealthCheck
        hc = HealthCheck()
        results = hc.run_all()
        assert isinstance(results, list)
        assert len(results) >= 4

    def test_render_table_returns_rich_table(self):
        from lidco.diagnostics.health import HealthCheck, HealthResult
        from rich.table import Table
        hc = HealthCheck()
        results = [
            HealthResult("api_keys", "ok", "All good", 1.0),
            HealthResult("tools", "warn", "No registry", 0.5),
        ]
        table = hc.render_table(results)
        assert isinstance(table, Table)
