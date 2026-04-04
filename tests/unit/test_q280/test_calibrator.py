"""Tests for metacog.calibrator."""
import unittest
from lidco.metacog.calibrator import ConfidenceCalibrator, Prediction


class TestConfidenceCalibrator(unittest.TestCase):

    def setUp(self):
        self.cal = ConfidenceCalibrator()

    def test_record_prediction(self):
        p = self.cal.record_prediction("p1", "yes", 0.8)
        self.assertIsInstance(p, Prediction)
        self.assertEqual(p.confidence, 0.8)

    def test_record_outcome(self):
        self.cal.record_prediction("p1", "yes", 0.8)
        p = self.cal.record_outcome("p1", "yes")
        self.assertIsNotNone(p)
        self.assertTrue(p.correct)

    def test_record_outcome_wrong(self):
        self.cal.record_prediction("p1", "yes", 0.8)
        p = self.cal.record_outcome("p1", "no")
        self.assertFalse(p.correct)

    def test_record_outcome_unknown(self):
        result = self.cal.record_outcome("nonexistent", "val")
        self.assertIsNone(result)

    def test_accuracy(self):
        self.cal.record_prediction("p1", "a", 0.9)
        self.cal.record_prediction("p2", "b", 0.9)
        self.cal.record_outcome("p1", "a")
        self.cal.record_outcome("p2", "c")
        self.assertEqual(self.cal.accuracy(), 0.5)

    def test_accuracy_empty(self):
        self.assertEqual(self.cal.accuracy(), 0.0)

    def test_brier_score(self):
        self.cal.record_prediction("p1", "a", 0.9)
        self.cal.record_outcome("p1", "a")
        score = self.cal.brier_score()
        self.assertLess(score, 0.1)  # high confidence + correct = low brier

    def test_brier_score_empty(self):
        self.assertEqual(self.cal.brier_score(), 0.0)

    def test_overconfident_detection(self):
        for i in range(10):
            self.cal.record_prediction(f"p{i}", "yes", 0.95)
            self.cal.record_outcome(f"p{i}", "no" if i < 7 else "yes")
        self.assertTrue(self.cal.is_overconfident())

    def test_not_overconfident_with_few(self):
        self.cal.record_prediction("p1", "a", 0.9)
        self.cal.record_outcome("p1", "b")
        self.assertFalse(self.cal.is_overconfident())

    def test_calibration_curve(self):
        for i in range(20):
            conf = i / 20
            self.cal.record_prediction(f"p{i}", "a", conf)
            self.cal.record_outcome(f"p{i}", "a" if i % 2 == 0 else "b")
        curve = self.cal.calibration_curve()
        self.assertGreater(len(curve), 0)
        self.assertIn("avg_confidence", curve[0])

    def test_calibration_curve_empty(self):
        self.assertEqual(self.cal.calibration_curve(), [])

    def test_confidence_clamped(self):
        p = self.cal.record_prediction("p1", "x", 1.5)
        self.assertEqual(p.confidence, 1.0)

    def test_summary(self):
        s = self.cal.summary()
        self.assertIn("total_predictions", s)
        self.assertIn("brier_score", s)

    def test_predictions_list(self):
        self.cal.record_prediction("p1", "a", 0.5)
        self.assertEqual(len(self.cal.predictions()), 1)


if __name__ == "__main__":
    unittest.main()
