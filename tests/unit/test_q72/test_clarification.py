"""Tests for clarification threshold and autonomy — T482."""
from __future__ import annotations
import pytest
from lidco.confidence.estimator import ConfidenceEstimator
from lidco.confidence.autonomy import AutonomyController, AutonomyMode


class TestClarificationThreshold:
    def test_default_threshold_07(self):
        est = ConfidenceEstimator()
        assert est.threshold == 0.7

    def test_custom_threshold(self):
        est = ConfidenceEstimator(threshold=0.5)
        assert est.threshold == 0.5

    def test_file_delete_asks_with_default_threshold(self):
        est = ConfidenceEstimator()
        score = est.score("file_delete", {}, "")
        assert score.should_ask

    def test_high_threshold_asks_more(self):
        est_low = ConfidenceEstimator(threshold=0.3)
        est_high = ConfidenceEstimator(threshold=0.95)
        score_low = est_low.score("file_read", {"path": "x"}, "read the configuration file for database settings")
        score_high = est_high.score("file_read", {"path": "x"}, "read the configuration file for database settings")
        # High threshold asks more often
        assert score_high.should_ask or not score_low.should_ask

    def test_zero_threshold_never_asks(self):
        est = ConfidenceEstimator(threshold=0.0)
        score = est.score("file_delete", {}, "")
        assert not score.should_ask
