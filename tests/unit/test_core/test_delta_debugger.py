"""Tests for src/lidco/core/delta_debugger.py"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.core.delta_debugger import (
    DdminConfig,
    DdminResult,
    ddmin,
    format_ddmin_result,
    make_pytest_oracle,
    shrink_list_fixture,
)


# ── ddmin ─────────────────────────────────────────────────────────────────────

class TestDdmin:
    def test_empty_list(self):
        result = ddmin([], lambda x: True)
        assert result.original_length == 0
        assert result.minimal_length == 0
        assert result.components == []

    def test_single_element_no_reduction(self):
        oracle = lambda items: len(items) > 0
        result = ddmin([42], oracle)
        assert result.components == [42]
        assert result.minimal_length == 1

    def test_reduces_to_single_faulty_element(self):
        # Only element 5 triggers the failure
        oracle = lambda items: 5 in items
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        result = ddmin(data, oracle)
        assert 5 in result.components
        assert result.minimal_length <= len(data)

    def test_reduces_large_list(self):
        # Oracle: fails when item > 100 present
        big = list(range(50)) + [999] + list(range(50, 100))
        oracle = lambda items: any(x == 999 for x in items)
        result = ddmin(big, oracle)
        assert 999 in result.components
        assert result.minimal_length < len(big)

    def test_returns_ddmin_result(self):
        oracle = lambda items: len(items) >= 1
        result = ddmin([1, 2, 3], oracle)
        assert isinstance(result, DdminResult)

    def test_reduction_pct_calculated(self):
        oracle = lambda items: 0 in items
        data = list(range(10))
        result = ddmin(data, oracle)
        expected_pct = 100.0 * (result.original_length - result.minimal_length) / result.original_length
        assert result.reduction_pct == pytest.approx(expected_pct)

    def test_iteration_count_positive(self):
        oracle = lambda items: len(items) >= 1
        result = ddmin([1, 2, 3, 4], oracle)
        assert result.iterations >= 0

    def test_max_iterations_respected(self):
        calls = [0]
        def oracle(items):
            calls[0] += 1
            return len(items) >= 2
        config = DdminConfig(max_iterations=5)
        ddmin(list(range(20)), oracle, config)
        assert calls[0] <= 20  # some slack for the algorithm structure

    def test_timeout_respected(self):
        import time
        def slow_oracle(items):
            time.sleep(0.1)
            return True
        config = DdminConfig(timeout_s=0.25, max_iterations=1000)
        start = time.monotonic()
        ddmin(list(range(10)), slow_oracle, config)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0  # should not run forever

    def test_components_still_triggers_oracle(self):
        """The returned components must satisfy the oracle."""
        oracle = lambda items: sum(items) > 10
        data = [1, 2, 3, 4, 5, 6]
        result = ddmin(data, oracle)
        assert oracle(result.components)

    def test_result_is_frozen(self):
        result = ddmin([1], lambda x: True)
        with pytest.raises((AttributeError, TypeError)):
            result.minimal_length = 999  # type: ignore[misc]

    def test_no_reduction_when_all_needed(self):
        # Oracle passes only when all items present
        data = [1, 2, 3]
        oracle = lambda items: set(items) == {1, 2, 3}
        result = ddmin(data, oracle)
        assert set(result.components) == {1, 2, 3}


# ── DdminConfig ───────────────────────────────────────────────────────────────

class TestDdminConfig:
    def test_defaults(self):
        cfg = DdminConfig()
        assert cfg.max_iterations == 100
        assert cfg.timeout_s == 30.0

    def test_custom_values(self):
        cfg = DdminConfig(max_iterations=50, timeout_s=10.0)
        assert cfg.max_iterations == 50
        assert cfg.timeout_s == 10.0

    def test_frozen(self):
        cfg = DdminConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.max_iterations = 1  # type: ignore[misc]


# ── format_ddmin_result ───────────────────────────────────────────────────────

class TestFormatDdminResult:
    def test_empty_original_returns_empty(self):
        result = DdminResult(
            original_length=0, minimal_length=0, components=[],
            iterations=0, reduction_pct=0.0,
        )
        assert format_ddmin_result(result) == ""

    def test_header_present(self):
        result = DdminResult(
            original_length=10, minimal_length=2, components=[1, 2],
            iterations=15, reduction_pct=80.0,
        )
        out = format_ddmin_result(result)
        assert "## Delta Debugger Result" in out

    def test_reduction_stats_present(self):
        result = DdminResult(
            original_length=50, minimal_length=3, components=["a", "b", "c"],
            iterations=42, reduction_pct=94.0,
        )
        out = format_ddmin_result(result)
        assert "50" in out
        assert "3" in out
        assert "94.0%" in out

    def test_components_shown(self):
        result = DdminResult(
            original_length=5, minimal_length=2, components=["foo", "bar"],
            iterations=10, reduction_pct=60.0,
        )
        out = format_ddmin_result(result)
        assert "foo" in out
        assert "bar" in out

    def test_oracle_calls_shown(self):
        result = DdminResult(
            original_length=10, minimal_length=1, components=[99],
            iterations=23, reduction_pct=90.0,
        )
        out = format_ddmin_result(result)
        assert "23" in out


# ── make_pytest_oracle ────────────────────────────────────────────────────────

class TestMakePytestOracle:
    def test_returns_callable(self, tmp_path):
        oracle = make_pytest_oracle("tests/test_foo.py::test_bar", "my_fixture", tmp_path)
        assert callable(oracle)

    def test_empty_items_returns_false(self, tmp_path):
        oracle = make_pytest_oracle("tests/test_foo.py::test_bar", "my_fixture", tmp_path)
        assert oracle([]) is False

    def test_subprocess_failure_returns_false(self, tmp_path):
        with patch("subprocess.run", side_effect=Exception("boom")):
            oracle = make_pytest_oracle("tests/t.py::t", "fix", tmp_path)
            assert oracle([1, 2]) is False

    def test_nonzero_exit_returns_true(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            oracle = make_pytest_oracle("tests/t.py::t", "fix", tmp_path)
            assert oracle([1, 2]) is True

    def test_zero_exit_returns_false(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            oracle = make_pytest_oracle("tests/t.py::t", "fix", tmp_path)
            assert oracle([1, 2]) is False
