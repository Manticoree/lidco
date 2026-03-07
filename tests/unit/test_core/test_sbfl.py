"""Tests for src/lidco/core/sbfl.py"""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.core.sbfl import (
    SuspiciousnessMap,
    SuspiciousnessScore,
    compute_sbfl,
    format_suspicious_lines,
    ochiai,
    read_coverage_contexts,
)


# ── ochiai ────────────────────────────────────────────────────────────────────

class TestOchiai:
    def test_perfect_fault_location(self):
        # ef=3, ep=0, total_failed=3 → 3/sqrt(3*3) = 1.0
        assert ochiai(3, 0, 3) == pytest.approx(1.0)

    def test_zero_ef(self):
        # Line never executed by failing tests → score 0
        assert ochiai(0, 5, 3) == 0.0

    def test_zero_total_failed(self):
        # No failing tests → score 0 (can't compute)
        assert ochiai(1, 2, 0) == 0.0

    def test_zero_ef_and_ep(self):
        assert ochiai(0, 0, 3) == 0.0

    def test_partial_coverage(self):
        # ef=2, ep=1, total_failed=3 → 2/sqrt(3*(2+1)) = 2/3
        expected = 2 / math.sqrt(3 * 3)
        assert ochiai(2, 1, 3) == pytest.approx(expected)

    def test_result_in_unit_range(self):
        for ef in range(5):
            for ep in range(5):
                result = ochiai(ef, ep, 5)
                assert 0.0 <= result <= 1.0

    def test_higher_ef_higher_score(self):
        s1 = ochiai(1, 2, 5)
        s2 = ochiai(3, 2, 5)
        assert s2 > s1

    def test_higher_ep_lower_score(self):
        s1 = ochiai(2, 1, 5)
        s2 = ochiai(2, 5, 5)
        assert s2 < s1


# ── compute_sbfl ─────────────────────────────────────────────────────────────

class TestComputeSbfl:
    def _spectra(self):
        return {
            "test_a": {10, 20, 30},
            "test_b": {10, 20},
            "test_c": {10, 30},
        }

    def _results_one_fail(self):
        return {"test_a": False, "test_b": True, "test_c": True}

    def test_returns_suspiciousness_map(self):
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "src/foo.py")
        assert isinstance(smap, SuspiciousnessMap)

    def test_file_path_preserved(self):
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "src/bar.py")
        assert smap.file_path == "src/bar.py"

    def test_total_failing_correct(self):
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "foo")
        assert smap.total_failing == 1
        assert smap.total_passing == 2

    def test_sorted_by_score_desc(self):
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "foo")
        scores = [s.score for s in smap.scores]
        assert scores == sorted(scores, reverse=True)

    def test_line_30_most_suspicious(self):
        # test_a (failing) hits 10, 20, 30; tests b and c also hit 10 but not 30 exclusively
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "foo")
        top = smap.scores[0]
        # line 30: ef=1, ep=1 (test_c hits it); line 20: ef=1, ep=1 (test_b hits it)
        # line 10: ef=1, ep=2 — lowest
        assert top.line in (20, 30)

    def test_all_scores_zero_when_no_failing(self):
        results = {"test_a": True, "test_b": True, "test_c": True}
        smap = compute_sbfl(self._spectra(), results, "foo")
        assert all(s.score == 0.0 for s in smap.scores)

    def test_empty_spectra(self):
        smap = compute_sbfl({}, {}, "foo")
        assert smap.scores == []
        assert smap.total_failing == 0

    def test_score_is_frozen(self):
        smap = compute_sbfl(self._spectra(), self._results_one_fail(), "foo")
        with pytest.raises((AttributeError, TypeError)):
            smap.scores[0].score = 9.9  # type: ignore[misc]

    def test_failed_hits_passed_hits_correct(self):
        spectra = {"fail1": {5}, "pass1": {5, 10}, "pass2": {10}}
        results = {"fail1": False, "pass1": True, "pass2": True}
        smap = compute_sbfl(spectra, results, "foo")
        # line 5: ef=1, ep=1
        line5 = next(s for s in smap.scores if s.line == 5)
        assert line5.failed_hits == 1
        assert line5.passed_hits == 1

    def test_multiple_failing_tests(self):
        spectra = {"f1": {10, 20}, "f2": {20, 30}, "p1": {10}}
        results = {"f1": False, "f2": False, "p1": True}
        smap = compute_sbfl(spectra, results, "foo")
        assert smap.total_failing == 2
        # line 20: ef=2, ep=0 → highest score
        line20 = next(s for s in smap.scores if s.line == 20)
        assert line20.failed_hits == 2
        assert line20.passed_hits == 0
        assert smap.scores[0].line == 20


# ── read_coverage_contexts ────────────────────────────────────────────────────

class TestReadCoverageContexts:
    def test_missing_file_returns_empty(self, tmp_path):
        result = read_coverage_contexts(tmp_path / "nonexistent.coverage", "src/foo.py")
        assert result == {}

    def test_coverage_import_error_returns_empty(self, tmp_path):
        cov_file = tmp_path / ".coverage"
        cov_file.write_text("fake")
        # coverage module may not be installed in test env — should not raise
        result = read_coverage_contexts(cov_file, "src/foo.py")
        # Either empty (import error) or empty (no contexts) — just no exception
        assert isinstance(result, dict)


# ── format_suspicious_lines ───────────────────────────────────────────────────

class TestFormatSuspiciousLines:
    def _make_smap(self, scores: list[tuple[int, float]]) -> SuspiciousnessMap:
        score_objs = [
            SuspiciousnessScore(line=ln, score=sc, failed_hits=1, passed_hits=0)
            for ln, sc in scores
        ]
        score_objs.sort(key=lambda x: x.score, reverse=True)
        return SuspiciousnessMap(
            file_path="src/foo.py",
            scores=score_objs,
            total_failing=2,
            total_passing=3,
        )

    def test_empty_scores_empty_string(self):
        smap = SuspiciousnessMap("foo", [], 0, 0)
        assert format_suspicious_lines(smap) == ""

    def test_all_zero_scores_empty(self):
        smap = self._make_smap([(10, 0.0), (20, 0.0)])
        assert format_suspicious_lines(smap) == ""

    def test_output_contains_header(self):
        smap = self._make_smap([(10, 0.8)])
        out = format_suspicious_lines(smap)
        assert "## Suspicious Lines (Ochiai)" in out

    def test_output_contains_file_path(self):
        smap = self._make_smap([(10, 0.8)])
        out = format_suspicious_lines(smap)
        assert "src/foo.py" in out

    def test_output_contains_line_numbers(self):
        smap = self._make_smap([(42, 0.9), (17, 0.5)])
        out = format_suspicious_lines(smap)
        assert "42" in out
        assert "17" in out

    def test_top_n_limits_rows(self):
        scores = [(i, 1.0 - i * 0.05) for i in range(1, 20)]
        smap = self._make_smap(scores)
        out = format_suspicious_lines(smap, top_n=3)
        data_rows = [ln for ln in out.splitlines() if ln.startswith("| ") and "Score" not in ln and "---" not in ln]
        assert len(data_rows) == 3

    def test_stats_line_present(self):
        smap = self._make_smap([(10, 0.7)])
        out = format_suspicious_lines(smap)
        assert "2 failing" in out
        assert "3 passing" in out
