"""Tests for lidco.testing.test_prioritizer — Task 980."""

import unittest

from lidco.testing.test_prioritizer import (
    ChangedFile,
    TestPrioritizer,
    TestPriority,
)


class TestTestPrioritizer(unittest.TestCase):
    def setUp(self):
        self.prio = TestPrioritizer()

    def test_prioritize_empty(self):
        result = self.prio.prioritize([], [])
        self.assertEqual(len(result), 0)

    def test_register_mapping(self):
        self.prio.register_mapping("src/foo.py", ["tests/test_foo.py"])
        self.assertIn("src/foo.py", self.prio.test_file_map)
        self.assertEqual(self.prio.test_file_map["src/foo.py"], ["tests/test_foo.py"])

    def test_register_failure(self):
        self.prio.register_failure("tests/test_foo.py", 3)
        self.assertEqual(self.prio.failure_history["tests/test_foo.py"], 3)

    def test_register_failure_accumulates(self):
        self.prio.register_failure("tests/test_foo.py", 2)
        self.prio.register_failure("tests/test_foo.py", 1)
        self.assertEqual(self.prio.failure_history["tests/test_foo.py"], 3)

    def test_prioritize_with_mapping(self):
        self.prio.register_mapping("src/foo.py", ["tests/test_foo.py"])
        changed = [ChangedFile(file_path="src/foo.py", added_lines=[1, 2, 3])]
        result = self.prio.prioritize(changed, ["tests/test_foo.py", "tests/test_bar.py"])
        self.assertEqual(result[0].test_path, "tests/test_foo.py")
        self.assertGreater(result[0].priority_score, result[1].priority_score)

    def test_prioritize_name_heuristic(self):
        changed = [ChangedFile(file_path="src/calculator.py")]
        result = self.prio.prioritize(changed, ["tests/test_calculator.py", "tests/test_other.py"])
        calc = [r for r in result if r.test_path == "tests/test_calculator.py"][0]
        self.assertGreaterEqual(calc.priority_score, 0.4)

    def test_prioritize_failure_boost(self):
        self.prio.register_failure("tests/test_a.py", 5)
        changed = [ChangedFile(file_path="src/a.py")]
        result = self.prio.prioritize(changed, ["tests/test_a.py"])
        tp = result[0]
        self.assertIn("failed", tp.reasons[-1])

    def test_get_ordered_tests(self):
        self.prio.register_mapping("src/x.py", ["tests/test_x.py"])
        changed = [ChangedFile(file_path="src/x.py", added_lines=[1])]
        ordered = self.prio.get_ordered_tests(changed, ["tests/test_x.py", "tests/test_y.py"])
        self.assertEqual(ordered[0], "tests/test_x.py")

    def test_infer_test_mapping(self):
        sources = ["src/cache.py", "src/config.py"]
        tests = ["tests/test_cache.py", "tests/test_config.py", "tests/test_other.py"]
        mapping = self.prio.infer_test_mapping(sources, tests)
        self.assertIn("src/cache.py", mapping)
        self.assertIn("tests/test_cache.py", mapping["src/cache.py"])

    def test_score_capped_at_one(self):
        self.prio.register_mapping("src/x.py", ["tests/test_x.py"])
        self.prio.register_failure("tests/test_x.py", 100)
        changed = [ChangedFile(file_path="src/x.py", added_lines=list(range(100)))]
        result = self.prio.prioritize(changed, ["tests/test_x.py"])
        self.assertLessEqual(result[0].priority_score, 1.0)

    def test_no_connection_gets_low_score(self):
        changed = [ChangedFile(file_path="src/something.py")]
        result = self.prio.prioritize(changed, ["tests/test_unrelated.py"])
        self.assertEqual(result[0].priority_score, 0.1)
        self.assertIn("no direct connection", result[0].reasons[0])

    def test_prioritize_multiple_reasons(self):
        self.prio.register_mapping("src/foo.py", ["tests/test_foo.py"])
        self.prio.register_failure("tests/test_foo.py", 2)
        changed = [ChangedFile(file_path="src/foo.py", added_lines=[1])]
        result = self.prio.prioritize(changed, ["tests/test_foo.py"])
        self.assertTrue(len(result[0].reasons) >= 2)

    def test_test_priority_dataclass(self):
        tp = TestPriority(
            test_path="tests/test_x.py", test_name="test_x.py",
            priority_score=0.7, reasons=["reason1"],
        )
        self.assertEqual(tp.test_path, "tests/test_x.py")
        self.assertEqual(tp.priority_score, 0.7)

    def test_changed_file_defaults(self):
        cf = ChangedFile(file_path="src/a.py")
        self.assertEqual(cf.added_lines, [])
        self.assertEqual(cf.removed_lines, [])
        self.assertFalse(cf.is_new)
        self.assertFalse(cf.is_deleted)

    def test_test_file_map_property_returns_copy(self):
        self.prio.register_mapping("src/a.py", ["tests/test_a.py"])
        map1 = self.prio.test_file_map
        map1["src/b.py"] = ["tests/test_b.py"]
        self.assertNotIn("src/b.py", self.prio.test_file_map)

    def test_failure_history_property_returns_copy(self):
        self.prio.register_failure("test_a.py", 1)
        hist = self.prio.failure_history
        hist["test_b.py"] = 5
        self.assertNotIn("test_b.py", self.prio.failure_history)

    def test_infer_mapping_no_match(self):
        sources = ["src/unique_module.py"]
        tests = ["tests/test_other.py"]
        mapping = self.prio.infer_test_mapping(sources, tests)
        self.assertNotIn("src/unique_module.py", mapping)

    def test_prioritize_deleted_file(self):
        self.prio.register_mapping("src/old.py", ["tests/test_old.py"])
        changed = [ChangedFile(file_path="src/old.py", is_deleted=True)]
        result = self.prio.prioritize(changed, ["tests/test_old.py"])
        self.assertEqual(len(result), 1)

    def test_multiple_changed_files(self):
        self.prio.register_mapping("src/a.py", ["tests/test_a.py"])
        self.prio.register_mapping("src/b.py", ["tests/test_b.py"])
        changed = [
            ChangedFile(file_path="src/a.py", added_lines=[1]),
            ChangedFile(file_path="src/b.py", added_lines=[1, 2, 3]),
        ]
        result = self.prio.prioritize(changed, ["tests/test_a.py", "tests/test_b.py"])
        self.assertEqual(len(result), 2)

    def test_ordered_tests_returns_list(self):
        ordered = self.prio.get_ordered_tests([], ["tests/a.py"])
        self.assertIsInstance(ordered, list)


if __name__ == "__main__":
    unittest.main()
