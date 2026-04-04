"""Tests for metacog.reflection."""
import unittest
from lidco.metacog.reflection import ReflectionEngine, Reflection


class TestReflectionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ReflectionEngine()

    def test_reflect_basic(self):
        r = self.engine.reflect("r1", "A detailed response about Python testing" * 5)
        self.assertIsInstance(r, Reflection)
        self.assertEqual(r.response_id, "r1")
        self.assertGreater(r.quality_score, 0.0)

    def test_short_response_flagged(self):
        r = self.engine.reflect("r2", "Short")
        self.assertTrue(any("brief" in w for w in r.what_didnt))

    def test_tools_used_positive(self):
        r = self.engine.reflect("r3", "Response text " * 20, tools_used=["Read", "Edit"])
        self.assertTrue(any("tool" in w.lower() for w in r.what_worked))

    def test_no_tools_for_code_task(self):
        r = self.engine.reflect("r4", "Response " * 20, task_type="code")
        self.assertTrue(any("tool" in w.lower() for w in r.what_didnt))

    def test_history(self):
        self.engine.reflect("r1", "Response 1 " * 20)
        self.engine.reflect("r2", "Response 2 " * 20)
        self.assertEqual(len(self.engine.history()), 2)

    def test_average_quality(self):
        self.engine.reflect("r1", "Good " * 100, tools_used=["Read"])
        avg = self.engine.average_quality()
        self.assertGreater(avg, 0.0)

    def test_average_quality_empty(self):
        self.assertEqual(self.engine.average_quality(), 0.0)

    def test_improvement_summary(self):
        self.engine.reflect("r1", "Short")
        self.engine.reflect("r2", "Short")
        imps = self.engine.improvement_summary()
        # Deduplication
        self.assertEqual(len(imps), len(set(imps)))

    def test_max_history(self):
        engine = ReflectionEngine(max_history=3)
        for i in range(5):
            engine.reflect(f"r{i}", "Some response " * 20)
        self.assertEqual(len(engine.history()), 3)

    def test_explanation_task(self):
        r = self.engine.reflect("r5", "Detailed explanation " * 50, task_type="explanation")
        self.assertTrue(any("explanation" in w.lower() for w in r.what_worked))


if __name__ == "__main__":
    unittest.main()
