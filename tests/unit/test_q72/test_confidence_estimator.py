"""Tests for ConfidenceEstimator — T481."""
from __future__ import annotations
import pytest
from lidco.confidence.estimator import ConfidenceEstimator, ConfidenceScore, _detect_conflict, _score_task_clarity


class TestConfidenceEstimator:
    def test_score_returns_confidence_score(self):
        est = ConfidenceEstimator()
        score = est.score("file_read", {}, "read the config file")
        assert isinstance(score, ConfidenceScore)
        assert 0.0 <= score.value <= 1.0

    def test_file_delete_low_confidence(self):
        est = ConfidenceEstimator()
        score = est.score("file_delete", {"path": "x.py"}, "delete it")
        assert score.value < 0.7

    def test_file_read_high_confidence(self):
        est = ConfidenceEstimator()
        score = est.score("file_read", {"path": "config.py"}, "read the config")
        assert score.value >= 0.6

    def test_should_ask_below_threshold(self):
        est = ConfidenceEstimator(threshold=0.7)
        score = est.score("file_delete", {}, "")
        assert score.should_ask

    def test_should_not_ask_above_threshold(self):
        est = ConfidenceEstimator(threshold=0.3)
        score = est.score("file_read", {"path": "x"}, "read x to understand it")
        assert not score.should_ask

    def test_factors_present(self):
        est = ConfidenceEstimator()
        score = est.score("bash", {"cmd": "ls"}, "list files")
        assert "task_clarity" in score.factors
        assert "action_risk" in score.factors
        assert "context_completeness" in score.factors
        assert "conflict_detected" in score.factors

    def test_threshold_setter_clamps(self):
        est = ConfidenceEstimator()
        est.threshold = 1.5
        assert est.threshold == 1.0
        est.threshold = -0.5
        assert est.threshold == 0.0

    def test_conflict_detected_reduces_confidence(self):
        est = ConfidenceEstimator()
        no_conflict = est.score("file_write", {"path": "x"}, "update the file")
        with_conflict = est.score("file_write", {"path": "x"}, "delete the file but keep it")
        assert with_conflict.value <= no_conflict.value

    def test_is_confident_property(self):
        est = ConfidenceEstimator(threshold=0.0)
        score = est.score("file_read", {}, "read file")
        assert score.is_confident

    def test_detect_conflict(self):
        assert _detect_conflict("delete the file but keep a backup")
        assert not _detect_conflict("just delete the file")

    def test_task_clarity_empty(self):
        assert _score_task_clarity("") < 0.5

    def test_task_clarity_detailed(self):
        assert _score_task_clarity("read the config.py file and extract the database URL") > 0.5
