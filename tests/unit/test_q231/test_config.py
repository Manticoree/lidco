"""Tests for lidco.budget.config."""
from __future__ import annotations

import pytest

from lidco.budget.config import BudgetConfig, BudgetConfigManager


class TestBudgetConfig:
    def test_frozen(self) -> None:
        c = BudgetConfig()
        with pytest.raises(AttributeError):
            c.context_limit = 256_000  # type: ignore[misc]

    def test_defaults(self) -> None:
        c = BudgetConfig()
        assert c.context_limit == 128_000
        assert c.warn_threshold == 0.70
        assert c.critical_threshold == 0.85
        assert c.emergency_threshold == 0.95
        assert c.max_tool_result_tokens == 2000
        assert c.debt_ceiling == 50_000
        assert c.auto_compact is True
        assert c.compact_strategy == "balanced"


class TestBudgetConfigManager:
    def test_get_default(self) -> None:
        mgr = BudgetConfigManager()
        cfg = mgr.get()
        assert cfg.context_limit == 128_000

    def test_get_with_model_no_override(self) -> None:
        mgr = BudgetConfigManager()
        cfg = mgr.get("gpt-4")
        assert cfg.context_limit == 128_000

    def test_set_and_get_override(self) -> None:
        mgr = BudgetConfigManager()
        custom = BudgetConfig(context_limit=200_000)
        mgr.set_override("claude-3", custom)
        assert mgr.get("claude-3").context_limit == 200_000
        assert mgr.get("gpt-4").context_limit == 128_000

    def test_remove_override_exists(self) -> None:
        mgr = BudgetConfigManager()
        mgr.set_override("m1", BudgetConfig(context_limit=50_000))
        assert mgr.remove_override("m1") is True
        assert mgr.get("m1").context_limit == 128_000

    def test_remove_override_not_exists(self) -> None:
        mgr = BudgetConfigManager()
        assert mgr.remove_override("nope") is False

    def test_list_overrides(self) -> None:
        mgr = BudgetConfigManager()
        mgr.set_override("a", BudgetConfig(context_limit=1))
        mgr.set_override("b", BudgetConfig(context_limit=2))
        overrides = mgr.list_overrides()
        assert len(overrides) == 2
        assert "a" in overrides
        assert "b" in overrides

    def test_from_dict(self) -> None:
        mgr = BudgetConfigManager()
        cfg = mgr.from_dict({"context_limit": 64_000, "auto_compact": False})
        assert cfg.context_limit == 64_000
        assert cfg.auto_compact is False
        assert cfg.warn_threshold == 0.70  # default preserved

    def test_to_dict(self) -> None:
        mgr = BudgetConfigManager()
        d = mgr.to_dict(BudgetConfig())
        assert d["context_limit"] == 128_000
        assert d["compact_strategy"] == "balanced"
        assert len(d) == 8

    def test_summary_returns_string(self) -> None:
        mgr = BudgetConfigManager()
        s = mgr.summary()
        assert "BudgetConfig" in s
        assert "128,000" in s

    def test_custom_default(self) -> None:
        custom = BudgetConfig(context_limit=256_000, compact_strategy="aggressive")
        mgr = BudgetConfigManager(default=custom)
        assert mgr.get().context_limit == 256_000
        assert mgr.get().compact_strategy == "aggressive"
