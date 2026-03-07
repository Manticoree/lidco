"""Tests for src/lidco/core/risk_scorer.py"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.core.risk_scorer import (
    RiskDimension,
    RiskScore,
    _label,
    _score_churn,
    _score_complexity,
    _score_coverage,
    _score_error_history,
    compute_risk_score,
    format_risk_report,
)


# ── _score_complexity ─────────────────────────────────────────────────────────

class TestScoreComplexity:
    def test_small_file_zero_score(self):
        dim = _score_complexity({"loc": 50})
        assert dim.score == 0
        assert "50" in dim.reason

    def test_moderate_file_score_5(self):
        dim = _score_complexity({"loc": 150})
        assert dim.score == 5

    def test_large_file_score_15(self):
        dim = _score_complexity({"loc": 250})
        assert dim.score == 15

    def test_very_large_file_score_25(self):
        dim = _score_complexity({"loc": 500})
        assert dim.score == 25

    def test_boundary_100(self):
        # exactly 100 → score 0 (not > 100)
        assert _score_complexity({"loc": 100}).score == 0

    def test_boundary_101(self):
        assert _score_complexity({"loc": 101}).score == 5

    def test_boundary_200(self):
        assert _score_complexity({"loc": 200}).score == 5

    def test_boundary_201(self):
        assert _score_complexity({"loc": 201}).score == 15

    def test_boundary_400(self):
        assert _score_complexity({"loc": 400}).score == 15

    def test_boundary_401(self):
        assert _score_complexity({"loc": 401}).score == 25

    def test_empty_metrics_zero(self):
        dim = _score_complexity({})
        assert dim.score == 0

    def test_none_loc_zero(self):
        dim = _score_complexity({"loc": None})
        assert dim.score == 0


# ── _score_churn ─────────────────────────────────────────────────────────────

class TestScoreChurn:
    def test_empty_git_log_zero(self):
        assert _score_churn("").score == 0

    def test_one_commit_score_5(self):
        assert _score_churn("abc123 fix thing\n").score == 5

    def test_three_commits_score_15(self):
        log = "a fix\nb fix\nc fix\n"
        assert _score_churn(log).score == 15

    def test_five_commits_score_25(self):
        log = "\n".join(f"commit{i} fix" for i in range(5))
        assert _score_churn(log).score == 25

    def test_six_commits_still_25(self):
        log = "\n".join(f"commit{i}" for i in range(6))
        assert _score_churn(log).score == 25

    def test_blank_lines_ignored(self):
        log = "abc fix\n\n\ndef fix\n"
        assert _score_churn(log).score == 5  # 2 non-blank → score 5

    def test_none_git_log_zero(self):
        assert _score_churn(None).score == 0  # type: ignore[arg-type]


# ── _score_coverage ───────────────────────────────────────────────────────────

class TestScoreCoverage:
    def _make_info(self, pct: float):
        info = MagicMock()
        info.coverage_pct = pct
        return info

    def test_no_data_zero(self):
        dim = _score_coverage("src/foo.py", {})
        assert dim.score == 0
        assert "No coverage" in dim.reason

    def test_very_low_coverage_25(self):
        info = self._make_info(30.0)
        dim = _score_coverage("src/foo.py", {"src/foo.py": info})
        assert dim.score == 25

    def test_low_coverage_15(self):
        info = self._make_info(55.0)
        dim = _score_coverage("src/foo.py", {"src/foo.py": info})
        assert dim.score == 15

    def test_moderate_coverage_5(self):
        info = self._make_info(70.0)
        dim = _score_coverage("src/foo.py", {"src/foo.py": info})
        assert dim.score == 5

    def test_well_covered_0(self):
        info = self._make_info(90.0)
        dim = _score_coverage("src/foo.py", {"src/foo.py": info})
        assert dim.score == 0

    def test_backslash_normalisation(self):
        info = self._make_info(25.0)
        dim = _score_coverage("src\\foo.py", {"src/foo.py": info})
        assert dim.score == 25


# ── _score_error_history ──────────────────────────────────────────────────────

class TestScoreErrorHistory:
    def _make_entry(self, message: str) -> dict:
        return {"sample_message": message, "total_occurrences": 1}

    def test_no_history_zero(self):
        dim = _score_error_history("src/foo.py", [])
        assert dim.score == 0

    def test_one_match_score_5(self):
        entries = [self._make_entry("Error in foo.py line 10")]
        dim = _score_error_history("src/foo.py", entries)
        assert dim.score == 5

    def test_two_matches_score_15(self):
        entries = [
            self._make_entry("Error in foo.py"),
            self._make_entry("Another error foo.py"),
        ]
        dim = _score_error_history("src/foo.py", entries)
        assert dim.score == 15

    def test_five_matches_score_25(self):
        entries = [self._make_entry("foo.py error")] * 5
        dim = _score_error_history("src/foo.py", entries)
        assert dim.score == 25

    def test_different_file_no_match(self):
        entries = [self._make_entry("Error in bar.py")]
        dim = _score_error_history("src/foo.py", entries)
        assert dim.score == 0


# ── _label ────────────────────────────────────────────────────────────────────

class TestLabel:
    def test_low(self):
        assert _label(0) == "LOW"
        assert _label(29) == "LOW"

    def test_medium(self):
        assert _label(30) == "MEDIUM"
        assert _label(59) == "MEDIUM"

    def test_high(self):
        assert _label(60) == "HIGH"
        assert _label(100) == "HIGH"


# ── compute_risk_score ────────────────────────────────────────────────────────

class TestComputeRiskScore:
    def test_all_zero(self):
        score = compute_risk_score("src/foo.py", {"loc": 10}, "", {}, [])
        assert score.total == 0
        assert score.label == "LOW"
        assert score.file_path == "src/foo.py"

    def test_total_is_sum(self):
        info = MagicMock()
        info.coverage_pct = 30.0
        score = compute_risk_score(
            "src/big.py",
            {"loc": 500},  # complexity=25
            "\n".join(f"c{i}" for i in range(5)),  # churn=25
            {"src/big.py": info},  # coverage=25
            [],  # error_history=0
        )
        assert score.total == 75
        assert score.label == "HIGH"

    def test_is_frozen_dataclass(self):
        score = compute_risk_score("x.py", {}, "", {}, [])
        with pytest.raises((AttributeError, TypeError)):
            score.total = 999  # type: ignore[misc]


# ── format_risk_report ────────────────────────────────────────────────────────

class TestFormatRiskReport:
    def _make_score(self, path: str, total: int) -> RiskScore:
        dim = RiskDimension(score=0, reason="")
        return RiskScore(
            file_path=path,
            total=total,
            complexity=dim,
            churn=dim,
            coverage=dim,
            error_history=dim,
            label=_label(total),
        )

    def test_empty_list(self):
        assert format_risk_report([]) == ""

    def test_all_zero_scores_empty(self):
        scores = [self._make_score("src/foo.py", 0)]
        assert format_risk_report(scores) == ""

    def test_table_header_present(self):
        scores = [self._make_score("src/foo.py", 70)]
        out = format_risk_report(scores)
        assert "## High-Risk Files" in out
        assert "| File |" in out

    def test_file_appears_in_output(self):
        scores = [self._make_score("src/bar.py", 50)]
        out = format_risk_report(scores)
        assert "src/bar.py" in out

    def test_top_n_limiting(self):
        scores = [self._make_score(f"src/f{i}.py", 60 - i) for i in range(10)]
        out = format_risk_report(scores, top_n=3)
        assert out.count("|") > 0
        # Only 3 data rows + header rows → ≤ 5 pipe-rows total
        data_rows = [ln for ln in out.splitlines() if ln.startswith("| `")]
        assert len(data_rows) == 3
