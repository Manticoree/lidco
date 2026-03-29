"""Tests for MaxModeManager (Task 710)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.composer.max_mode import (
    MaxMode,
    ModeConfig,
    MODE_CONFIGS,
    UsageSummary,
    MaxModeManager,
)


class TestMaxModeEnum(unittest.TestCase):
    def test_normal_value(self):
        assert MaxMode.NORMAL.value == "normal"

    def test_max_value(self):
        assert MaxMode.MAX.value == "max"

    def test_mini_value(self):
        assert MaxMode.MINI.value == "mini"

    def test_all_modes_in_configs(self):
        for mode in MaxMode:
            assert mode in MODE_CONFIGS


class TestModeConfig(unittest.TestCase):
    def test_normal_config(self):
        cfg = MODE_CONFIGS[MaxMode.NORMAL]
        assert cfg.mode == MaxMode.NORMAL
        assert cfg.base_budget == 32_000
        assert cfg.max_tool_calls == 25
        assert cfg.extended_timeout is False

    def test_max_config(self):
        cfg = MODE_CONFIGS[MaxMode.MAX]
        assert cfg.mode == MaxMode.MAX
        assert cfg.base_budget == 200_000
        assert cfg.max_tool_calls == 200
        assert cfg.extended_timeout is True

    def test_mini_config(self):
        cfg = MODE_CONFIGS[MaxMode.MINI]
        assert cfg.mode == MaxMode.MINI
        assert cfg.base_budget == 8_000
        assert cfg.max_tool_calls == 10
        assert cfg.extended_timeout is False


class TestMaxModeManager(unittest.TestCase):
    def test_default_mode_is_normal(self):
        mgr = MaxModeManager()
        assert mgr.active_mode == MaxMode.NORMAL

    def test_config_property(self):
        mgr = MaxModeManager()
        cfg = mgr.config
        assert cfg.mode == MaxMode.NORMAL
        assert cfg.base_budget == 32_000

    def test_activate_max_string(self):
        mgr = MaxModeManager()
        cfg = mgr.activate("max")
        assert mgr.active_mode == MaxMode.MAX
        assert cfg.base_budget == 200_000

    def test_activate_mini_string(self):
        mgr = MaxModeManager()
        cfg = mgr.activate("mini")
        assert mgr.active_mode == MaxMode.MINI
        assert cfg.max_tool_calls == 10

    def test_activate_normal_string(self):
        mgr = MaxModeManager()
        mgr.activate("max")
        cfg = mgr.activate("normal")
        assert mgr.active_mode == MaxMode.NORMAL

    def test_activate_with_enum(self):
        mgr = MaxModeManager()
        cfg = mgr.activate(MaxMode.MAX)
        assert mgr.active_mode == MaxMode.MAX

    def test_activate_updates_adaptive_budget(self):
        ab = MagicMock()
        ab.base_budget = 4096
        mgr = MaxModeManager(adaptive_budget=ab)
        mgr.activate("max")
        assert ab.base_budget == 200_000

    def test_activate_updates_composer_session(self):
        cs = MagicMock()
        cs.max_tool_calls = 25
        mgr = MaxModeManager(composer_session=cs)
        mgr.activate("max")
        assert cs.max_tool_calls == 200

    def test_activate_none_adaptive_budget_no_error(self):
        mgr = MaxModeManager(adaptive_budget=None)
        cfg = mgr.activate("max")
        assert cfg.base_budget == 200_000

    def test_activate_none_composer_session_no_error(self):
        mgr = MaxModeManager(composer_session=None)
        cfg = mgr.activate("max")
        assert cfg.max_tool_calls == 200

    def test_record_usage(self):
        mgr = MaxModeManager()
        mgr.record_usage(100, 5)
        summary = mgr.usage_summary()
        assert summary.tokens_used == 100
        assert summary.tool_calls_made == 5

    def test_record_usage_accumulates(self):
        mgr = MaxModeManager()
        mgr.record_usage(100, 2)
        mgr.record_usage(50, 3)
        summary = mgr.usage_summary()
        assert summary.tokens_used == 150
        assert summary.tool_calls_made == 5

    def test_usage_summary_type(self):
        mgr = MaxModeManager()
        summary = mgr.usage_summary()
        assert isinstance(summary, UsageSummary)

    def test_usage_summary_current_mode(self):
        mgr = MaxModeManager()
        mgr.activate("mini")
        summary = mgr.usage_summary()
        assert summary.current_mode == "mini"

    def test_reset_usage(self):
        mgr = MaxModeManager()
        mgr.record_usage(500, 10)
        mgr.reset_usage()
        summary = mgr.usage_summary()
        assert summary.tokens_used == 0
        assert summary.tool_calls_made == 0

    def test_reset_usage_preserves_mode(self):
        mgr = MaxModeManager()
        mgr.activate("max")
        mgr.record_usage(100)
        mgr.reset_usage()
        assert mgr.active_mode == MaxMode.MAX

    def test_mode_history_recorded(self):
        mgr = MaxModeManager()
        mgr.activate("max")
        mgr.activate("mini")
        summary = mgr.usage_summary()
        assert len(summary.mode_history) == 2

    def test_mode_history_contains_mode_name(self):
        mgr = MaxModeManager()
        mgr.activate("max")
        summary = mgr.usage_summary()
        assert summary.mode_history[0]["mode"] == "max"

    def test_mode_history_contains_timestamp(self):
        mgr = MaxModeManager()
        mgr.activate("max")
        summary = mgr.usage_summary()
        assert "timestamp" in summary.mode_history[0]

    def test_activate_returns_mode_config(self):
        mgr = MaxModeManager()
        result = mgr.activate("max")
        assert isinstance(result, ModeConfig)

    def test_composer_session_without_max_tool_calls_attr(self):
        cs = MagicMock(spec=[])  # no attributes
        mgr = MaxModeManager(composer_session=cs)
        # should not raise
        mgr.activate("max")

    def test_usage_summary_empty_history(self):
        mgr = MaxModeManager()
        summary = mgr.usage_summary()
        assert summary.mode_history == []

    def test_record_usage_zero(self):
        mgr = MaxModeManager()
        mgr.record_usage(0, 0)
        summary = mgr.usage_summary()
        assert summary.tokens_used == 0


if __name__ == "__main__":
    unittest.main()
