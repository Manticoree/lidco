"""Tests for lidco.e2e_intel.optimizer — E2ETestOptimizer."""

from __future__ import annotations

import unittest

from lidco.e2e_intel.optimizer import (
    E2ETestOptimizer,
    IsolationLevel,
    OptimizationReport,
    ParallelGroup,
    SelectionResult,
    SharedSetup,
    TestMetadata,
)


class TestIsolationLevelEnum(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(IsolationLevel.NONE.value, "none")
        self.assertEqual(IsolationLevel.SHARED_STATE.value, "shared_state")
        self.assertEqual(IsolationLevel.FRESH_CONTEXT.value, "fresh_context")
        self.assertEqual(IsolationLevel.FULL_ISOLATION.value, "full_isolation")


class TestTestMetadata(unittest.TestCase):
    def test_frozen(self) -> None:
        m = TestMetadata(name="t", duration_ms=100)
        with self.assertRaises(AttributeError):
            m.name = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        m = TestMetadata(name="t", duration_ms=50)
        self.assertEqual(m.tags, ())
        self.assertEqual(m.depends_on, ())
        self.assertEqual(m.changed_files, ())
        self.assertEqual(m.last_result, "pass")


class TestParallelGroup(unittest.TestCase):
    def test_frozen(self) -> None:
        g = ParallelGroup(group_id=0, tests=("a",), estimated_duration_ms=100)
        with self.assertRaises(AttributeError):
            g.group_id = 1  # type: ignore[misc]


class TestSharedSetup(unittest.TestCase):
    def test_frozen(self) -> None:
        s = SharedSetup(name="s", tests=("a", "b"))
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]


class TestE2ETestOptimizer(unittest.TestCase):
    def test_default_max_parallel(self) -> None:
        opt = E2ETestOptimizer()
        self.assertEqual(opt.max_parallel, 4)

    def test_custom_max_parallel(self) -> None:
        opt = E2ETestOptimizer(max_parallel=8)
        self.assertEqual(opt.max_parallel, 8)

    # -- Parallel groups -----------------------------------------------------

    def test_parallel_groups_empty(self) -> None:
        opt = E2ETestOptimizer()
        groups = opt.compute_parallel_groups([])
        self.assertEqual(groups, [])

    def test_parallel_groups_no_deps(self) -> None:
        opt = E2ETestOptimizer(max_parallel=2)
        tests = [
            TestMetadata(name="a", duration_ms=100),
            TestMetadata(name="b", duration_ms=200),
            TestMetadata(name="c", duration_ms=150),
        ]
        groups = opt.compute_parallel_groups(tests)
        self.assertGreater(len(groups), 0)
        all_tests = set()
        for g in groups:
            all_tests.update(g.tests)
        self.assertEqual(all_tests, {"a", "b", "c"})

    def test_parallel_groups_respects_max(self) -> None:
        opt = E2ETestOptimizer(max_parallel=2)
        tests = [
            TestMetadata(name="a", duration_ms=100),
            TestMetadata(name="b", duration_ms=100),
            TestMetadata(name="c", duration_ms=100),
        ]
        groups = opt.compute_parallel_groups(tests)
        for g in groups:
            self.assertLessEqual(len(g.tests), 2)

    def test_parallel_groups_with_deps(self) -> None:
        opt = E2ETestOptimizer(max_parallel=4)
        tests = [
            TestMetadata(name="a", duration_ms=100),
            TestMetadata(name="b", duration_ms=100, depends_on=("a",)),
        ]
        groups = opt.compute_parallel_groups(tests)
        # 'a' must be in an earlier group than 'b'
        a_group = next(g.group_id for g in groups if "a" in g.tests)
        b_group = next(g.group_id for g in groups if "b" in g.tests)
        self.assertLess(a_group, b_group)

    # -- Shared setups -------------------------------------------------------

    def test_shared_setups_empty(self) -> None:
        opt = E2ETestOptimizer()
        setups = opt.detect_shared_setups([])
        self.assertEqual(setups, [])

    def test_shared_setups_detected(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=1000, tags=("auth",)),
            TestMetadata(name="b", duration_ms=2000, tags=("auth",)),
            TestMetadata(name="c", duration_ms=500, tags=("search",)),
        ]
        setups = opt.detect_shared_setups(tests)
        self.assertEqual(len(setups), 1)
        self.assertEqual(setups[0].name, "shared_setup_auth")
        self.assertIn("a", setups[0].tests)
        self.assertIn("b", setups[0].tests)

    def test_no_shared_setup_for_single_test(self) -> None:
        opt = E2ETestOptimizer()
        tests = [TestMetadata(name="a", duration_ms=100, tags=("unique",))]
        setups = opt.detect_shared_setups(tests)
        self.assertEqual(setups, [])

    # -- Selective running ---------------------------------------------------

    def test_select_all_when_no_changed_files(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=100),
            TestMetadata(name="b", duration_ms=200),
        ]
        result = opt.select_tests(tests, [])
        self.assertEqual(len(result.selected), 2)
        self.assertEqual(len(result.skipped), 0)

    def test_select_affected_by_changed_files(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(
                name="a", duration_ms=100, changed_files=("login.py",)
            ),
            TestMetadata(
                name="b", duration_ms=200, changed_files=("search.py",)
            ),
        ]
        result = opt.select_tests(tests, ["login.py"])
        self.assertIn("a", result.selected)
        self.assertIn("b", result.skipped)

    def test_select_always_includes_failed(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=100, last_result="fail"),
            TestMetadata(name="b", duration_ms=200),
        ]
        result = opt.select_tests(tests, ["unrelated.py"])
        self.assertIn("a", result.selected)

    def test_select_fallback_when_no_matches(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=100, changed_files=("x.py",)),
        ]
        result = opt.select_tests(tests, ["unrelated.py"])
        self.assertEqual(len(result.selected), 1)  # fallback to all

    # -- Isolation recommendations -------------------------------------------

    def test_recommend_isolation_default(self) -> None:
        opt = E2ETestOptimizer(
            isolation_default=IsolationLevel.FRESH_CONTEXT
        )
        tests = [TestMetadata(name="a", duration_ms=100)]
        recs = opt.recommend_isolation(tests)
        self.assertEqual(recs, [("a", IsolationLevel.FRESH_CONTEXT)])

    def test_recommend_isolation_shared_state_for_deps(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=100, depends_on=("b",)),
        ]
        recs = opt.recommend_isolation(tests)
        self.assertEqual(recs[0][1], IsolationLevel.SHARED_STATE)

    def test_recommend_isolation_full_for_failed(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(name="a", duration_ms=100, last_result="fail"),
        ]
        recs = opt.recommend_isolation(tests)
        self.assertEqual(recs[0][1], IsolationLevel.FULL_ISOLATION)

    # -- Full optimization ---------------------------------------------------

    def test_optimize_empty(self) -> None:
        opt = E2ETestOptimizer()
        report = opt.optimize([])
        self.assertEqual(report.parallel_groups, ())
        self.assertEqual(report.shared_setups, ())
        self.assertAlmostEqual(report.estimated_speedup, 1.0)

    def test_optimize_full(self) -> None:
        opt = E2ETestOptimizer(max_parallel=2)
        tests = [
            TestMetadata(name="a", duration_ms=1000, tags=("auth",)),
            TestMetadata(name="b", duration_ms=2000, tags=("auth",)),
            TestMetadata(name="c", duration_ms=500),
        ]
        report = opt.optimize(tests, changed_files=["auth.py"])
        self.assertIsInstance(report, OptimizationReport)
        self.assertGreater(len(report.parallel_groups), 0)
        self.assertGreater(report.estimated_speedup, 1.0)
        self.assertGreater(report.original_duration_ms, 0)

    def test_optimize_with_changed_files(self) -> None:
        opt = E2ETestOptimizer()
        tests = [
            TestMetadata(
                name="a", duration_ms=100, changed_files=("f.py",)
            ),
            TestMetadata(name="b", duration_ms=200),
        ]
        report = opt.optimize(tests, changed_files=["f.py"])
        self.assertIn("a", report.selection.selected)

    def test_optimize_isolation_recs_present(self) -> None:
        opt = E2ETestOptimizer()
        tests = [TestMetadata(name="a", duration_ms=100)]
        report = opt.optimize(tests)
        self.assertEqual(len(report.isolation_recommendations), 1)


if __name__ == "__main__":
    unittest.main()
