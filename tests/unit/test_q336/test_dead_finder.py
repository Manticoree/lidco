"""Tests for lidco.archaeology.dead_finder — DeadFeatureFinder."""

from __future__ import annotations

import unittest

from lidco.archaeology.dead_finder import (
    DeadFeature,
    DeadFeatureFinder,
    DeadFeatureReport,
    DeadKind,
)


class TestDeadKind(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(DeadKind.UNUSED_FUNCTION.value, "unused_function")
        self.assertEqual(DeadKind.STALE_FLAG.value, "stale_flag")
        self.assertEqual(DeadKind.DEAD_ENDPOINT.value, "dead_endpoint")


class TestDeadFeature(unittest.TestCase):
    def test_is_high_confidence_true(self) -> None:
        f = DeadFeature(kind=DeadKind.STALE_FLAG, name="f", file="x", line=1, confidence=0.9)
        self.assertTrue(f.is_high_confidence())

    def test_is_high_confidence_false(self) -> None:
        f = DeadFeature(kind=DeadKind.STALE_FLAG, name="f", file="x", line=1, confidence=0.5)
        self.assertFalse(f.is_high_confidence())

    def test_label(self) -> None:
        f = DeadFeature(kind=DeadKind.UNUSED_FUNCTION, name="old_func", file="a.py", line=10, confidence=0.7)
        label = f.label()
        self.assertIn("unused_function", label)
        self.assertIn("old_func", label)
        self.assertIn("a.py:10", label)

    def test_frozen(self) -> None:
        f = DeadFeature(kind=DeadKind.STALE_FLAG, name="f", file="x", line=1)
        with self.assertRaises(AttributeError):
            f.name = "y"  # type: ignore[misc]


class TestDeadFeatureReport(unittest.TestCase):
    def test_count_empty(self) -> None:
        r = DeadFeatureReport()
        self.assertEqual(r.count, 0)

    def test_count(self) -> None:
        features = [
            DeadFeature(kind=DeadKind.STALE_FLAG, name="a", file="x", line=1, confidence=0.9),
            DeadFeature(kind=DeadKind.UNUSED_FUNCTION, name="b", file="y", line=2, confidence=0.5),
        ]
        r = DeadFeatureReport(features=features, files_scanned=2)
        self.assertEqual(r.count, 2)

    def test_high_confidence_count(self) -> None:
        features = [
            DeadFeature(kind=DeadKind.STALE_FLAG, name="a", file="x", line=1, confidence=0.9),
            DeadFeature(kind=DeadKind.UNUSED_FUNCTION, name="b", file="y", line=2, confidence=0.5),
        ]
        r = DeadFeatureReport(features=features, files_scanned=2)
        self.assertEqual(r.high_confidence_count, 1)

    def test_by_kind(self) -> None:
        features = [
            DeadFeature(kind=DeadKind.STALE_FLAG, name="a", file="x", line=1),
            DeadFeature(kind=DeadKind.UNUSED_FUNCTION, name="b", file="y", line=2),
            DeadFeature(kind=DeadKind.STALE_FLAG, name="c", file="z", line=3),
        ]
        r = DeadFeatureReport(features=features)
        self.assertEqual(len(r.by_kind(DeadKind.STALE_FLAG)), 2)

    def test_by_file(self) -> None:
        features = [
            DeadFeature(kind=DeadKind.STALE_FLAG, name="a", file="x.py", line=1),
            DeadFeature(kind=DeadKind.UNUSED_FUNCTION, name="b", file="x.py", line=2),
            DeadFeature(kind=DeadKind.STALE_FLAG, name="c", file="y.py", line=3),
        ]
        r = DeadFeatureReport(features=features)
        self.assertEqual(len(r.by_file("x.py")), 2)

    def test_summary(self) -> None:
        features = [
            DeadFeature(kind=DeadKind.STALE_FLAG, name="a", file="x", line=1, confidence=0.9),
        ]
        r = DeadFeatureReport(features=features, files_scanned=5)
        s = r.summary()
        self.assertIn("1 items", s)
        self.assertIn("5 files", s)


class TestDeadFeatureFinder(unittest.TestCase):
    def test_file_count_empty(self) -> None:
        finder = DeadFeatureFinder()
        self.assertEqual(finder.file_count, 0)

    def test_add_file(self) -> None:
        finder = DeadFeatureFinder()
        finder.add_file("a.py", "x = 1")
        self.assertEqual(finder.file_count, 1)

    def test_scan_empty(self) -> None:
        finder = DeadFeatureFinder()
        report = finder.scan()
        self.assertEqual(report.count, 0)
        self.assertEqual(report.files_scanned, 0)

    def test_find_unused_function(self) -> None:
        code = "def used():\n    pass\n\ndef orphan():\n    pass\n\nused()\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unused = report.by_kind(DeadKind.UNUSED_FUNCTION)
        names = [f.name for f in unused]
        self.assertIn("orphan", names)
        self.assertNotIn("used", names)

    def test_private_functions_skipped(self) -> None:
        code = "def _private():\n    pass\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unused = report.by_kind(DeadKind.UNUSED_FUNCTION)
        names = [f.name for f in unused]
        self.assertNotIn("_private", names)

    def test_find_stale_flags(self) -> None:
        code = "if FEATURE_A:\n    do_a()\n"
        finder = DeadFeatureFinder(
            files={"a.py": code},
            flag_names=["FEATURE_A", "FEATURE_B"],
        )
        report = finder.scan()
        stale = report.by_kind(DeadKind.STALE_FLAG)
        names = [f.name for f in stale]
        self.assertIn("FEATURE_B", names)
        self.assertNotIn("FEATURE_A", names)

    def test_find_dead_endpoints(self) -> None:
        code = 'app.route("/api/users")\ndef users(): pass\n'
        finder = DeadFeatureFinder(
            files={"app.py": code},
            endpoint_paths=["/api/users", "/api/legacy"],
        )
        report = finder.scan()
        dead = report.by_kind(DeadKind.DEAD_ENDPOINT)
        names = [f.name for f in dead]
        self.assertIn("/api/legacy", names)
        self.assertNotIn("/api/users", names)

    def test_find_unreachable_code(self) -> None:
        code = "def f():\n    return 1\n    x = 2\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unreachable = report.by_kind(DeadKind.UNREACHABLE_CODE)
        self.assertTrue(len(unreachable) > 0)

    def test_unreachable_code_except_ok(self) -> None:
        # Code after return in a try block with except is OK
        code = "try:\n    return 1\nexcept:\n    pass\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unreachable = report.by_kind(DeadKind.UNREACHABLE_CODE)
        self.assertEqual(len(unreachable), 0)

    def test_find_unused_imports(self) -> None:
        code = "import os\nimport sys\nprint(sys.argv)\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unused = report.by_kind(DeadKind.UNUSED_IMPORT)
        names = [f.name for f in unused]
        self.assertIn("os", names)
        self.assertNotIn("sys", names)

    def test_find_unused_import_alias(self) -> None:
        code = "import numpy as np\nx = 1\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unused = report.by_kind(DeadKind.UNUSED_IMPORT)
        names = [f.name for f in unused]
        self.assertIn("np", names)

    def test_scan_multiple_files(self) -> None:
        files = {
            "a.py": "def lonely():\n    pass\n",
            "b.py": "x = 1\n",
        }
        finder = DeadFeatureFinder(files=files)
        report = finder.scan()
        self.assertEqual(report.files_scanned, 2)

    def test_async_function_detected(self) -> None:
        code = "async def orphan_async():\n    pass\n"
        finder = DeadFeatureFinder(files={"a.py": code})
        report = finder.scan()
        unused = report.by_kind(DeadKind.UNUSED_FUNCTION)
        names = [f.name for f in unused]
        self.assertIn("orphan_async", names)


if __name__ == "__main__":
    unittest.main()
