"""Tests for Q148 OrphanDetector."""
from __future__ import annotations

import unittest
from lidco.maintenance.orphan_detector import OrphanDetector, OrphanedResource


class TestOrphanedResource(unittest.TestCase):
    def test_fields(self):
        r = OrphanedResource(path="a.py", resource_type="file", reason="unused", suggestion="remove")
        self.assertEqual(r.path, "a.py")
        self.assertEqual(r.resource_type, "file")
        self.assertEqual(r.reason, "unused")
        self.assertEqual(r.suggestion, "remove")


class TestDetectUnusedFiles(unittest.TestCase):
    def setUp(self):
        self.det = OrphanDetector()

    def test_no_orphans_when_all_imported(self):
        files = ["a.py", "b.py"]
        import_map = {"a.py": ["b.py"], "b.py": ["a.py"]}
        result = self.det.detect_unused_files(files, import_map)
        self.assertEqual(result, [])

    def test_orphan_file_detected(self):
        files = ["a.py", "b.py", "c.py"]
        import_map = {"a.py": ["b.py"]}
        result = self.det.detect_unused_files(files, import_map)
        paths = [r.path for r in result]
        self.assertIn("c.py", paths)

    def test_file_in_import_map_keys_not_orphan(self):
        files = ["a.py", "b.py"]
        import_map = {"a.py": ["b.py"]}
        result = self.det.detect_unused_files(files, import_map)
        paths = [r.path for r in result]
        self.assertNotIn("a.py", paths)

    def test_resource_type_is_file(self):
        files = ["orphan.py"]
        import_map = {}
        result = self.det.detect_unused_files(files, import_map)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].resource_type, "file")

    def test_empty_file_list(self):
        result = self.det.detect_unused_files([], {"a.py": ["b.py"]})
        self.assertEqual(result, [])

    def test_empty_import_map(self):
        result = self.det.detect_unused_files(["a.py"], {})
        self.assertEqual(len(result), 1)

    def test_imported_by_multiple(self):
        files = ["a.py", "b.py", "c.py"]
        import_map = {"a.py": ["c.py"], "b.py": ["c.py"]}
        result = self.det.detect_unused_files(files, import_map)
        paths = [r.path for r in result]
        self.assertNotIn("c.py", paths)


class TestDetectDeadConfigs(unittest.TestCase):
    def setUp(self):
        self.det = OrphanDetector()

    def test_all_used(self):
        config = {"db_host": "localhost", "port": 8080}
        used = {"db_host", "port"}
        result = self.det.detect_dead_configs(config, used)
        self.assertEqual(result, [])

    def test_dead_key_detected(self):
        config = {"db_host": "localhost", "old_key": "value"}
        used = {"db_host"}
        result = self.det.detect_dead_configs(config, used)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, "old_key")
        self.assertEqual(result[0].resource_type, "config")

    def test_empty_config(self):
        result = self.det.detect_dead_configs({}, {"a"})
        self.assertEqual(result, [])

    def test_no_used_keys(self):
        config = {"a": 1, "b": 2}
        result = self.det.detect_dead_configs(config, set())
        self.assertEqual(len(result), 2)

    def test_suggestion_includes_key(self):
        config = {"stale": "v"}
        result = self.det.detect_dead_configs(config, set())
        self.assertIn("stale", result[0].suggestion)


class TestDetectAll(unittest.TestCase):
    def setUp(self):
        self.det = OrphanDetector()

    def test_combines_files_and_configs(self):
        files = ["orphan.py"]
        import_map = {}
        config = {"dead": "v"}
        used = set()
        result = self.det.detect_all(files, import_map, config, used)
        types = {r.resource_type for r in result}
        self.assertIn("file", types)
        self.assertIn("config", types)

    def test_no_config_args(self):
        result = self.det.detect_all(["a.py"], {})
        self.assertEqual(len(result), 1)

    def test_empty_everything(self):
        result = self.det.detect_all([], {}, {}, set())
        self.assertEqual(result, [])


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.det = OrphanDetector()

    def test_no_orphans(self):
        s = self.det.summary([])
        self.assertIn("No orphaned", s)

    def test_summary_counts(self):
        orphans = [
            OrphanedResource("a.py", "file", "unused", "remove"),
            OrphanedResource("b", "config", "dead", "remove"),
        ]
        s = self.det.summary(orphans)
        self.assertIn("2", s)
        self.assertIn("file", s)
        self.assertIn("config", s)

    def test_summary_includes_paths(self):
        orphans = [OrphanedResource("special.py", "file", "unused", "rm")]
        s = self.det.summary(orphans)
        self.assertIn("special.py", s)


if __name__ == "__main__":
    unittest.main()
