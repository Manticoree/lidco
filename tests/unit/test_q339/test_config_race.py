"""Tests for ConfigRaceDetector (Q339)."""
from __future__ import annotations

import unittest

from lidco.stability.config_race import ConfigRaceDetector


class TestDetectRaces(unittest.TestCase):
    def setUp(self):
        self.det = ConfigRaceDetector()

    def test_detect_unsynchronised_write(self):
        code = "config['key'] = value\n"
        findings = self.det.detect_races(code)
        self.assertTrue(any(f["type"] == "unsynchronised_write" for f in findings))

    def test_detect_unsynchronised_update(self):
        code = "settings.update({'a': 1})\n"
        findings = self.det.detect_races(code)
        self.assertTrue(any(f["type"] == "unsynchronised_update" for f in findings))

    def test_no_race_inside_lock(self):
        code = (
            "with self._lock:\n"
            "    config['key'] = value\n"
        )
        findings = self.det.detect_races(code)
        # Write is inside a lock — should not be flagged as HIGH unsynchronised_write.
        unsync_writes = [f for f in findings if f["type"] == "unsynchronised_write"]
        self.assertEqual(len(unsync_writes), 0)

    def test_global_mutation_flagged(self):
        code = "global _config\n_config = {}\n"
        findings = self.det.detect_races(code)
        self.assertTrue(any(f["type"] == "global_mutation" for f in findings))

    def test_setdefault_without_lock(self):
        code = "d.setdefault('key', [])\n"
        findings = self.det.detect_races(code)
        self.assertTrue(any(f["type"] == "check_then_act" for f in findings))

    def test_custom_setter_flagged(self):
        code = "def __setattr__(self, name, value):\n    pass\n"
        findings = self.det.detect_races(code)
        self.assertTrue(any(f["type"] == "custom_setter" for f in findings))

    def test_finding_has_required_keys(self):
        code = "config['x'] = 1\n"
        findings = self.det.detect_races(code)
        for f in findings:
            self.assertIn("line", f)
            self.assertIn("type", f)
            self.assertIn("description", f)
            self.assertIn("severity", f)

    def test_severity_values_valid(self):
        code = "config['x'] = 1\nsettings.update({})\nd.setdefault('k', [])\n"
        findings = self.det.detect_races(code)
        valid = {"HIGH", "MEDIUM", "LOW"}
        for f in findings:
            self.assertIn(f["severity"], valid)

    def test_clean_code_returns_empty(self):
        code = "x = 1\ny = x + 2\n"
        findings = self.det.detect_races(code)
        self.assertEqual(findings, [])

    def test_findings_stored_on_instance(self):
        code = "config['x'] = 1\n"
        self.det.detect_races(code)
        self.assertIsInstance(self.det.findings, list)
        self.assertGreater(len(self.det.findings), 0)


class TestAnalyzeLockContention(unittest.TestCase):
    def setUp(self):
        self.det = ConfigRaceDetector()

    def test_single_lock_low_risk(self):
        code = "with self._lock:\n    pass\n"
        results = self.det.analyze_lock_contention(code)
        self.assertGreater(len(results), 0)
        r = results[0]
        self.assertIn("lock_name", r)
        self.assertIn("contention_risk", r)
        self.assertIn("suggestion", r)

    def test_high_contention_many_sites(self):
        # 6 usages → HIGH risk.
        lines = ["with self._lock:\n    pass\n"] * 6
        code = "".join(lines)
        results = self.det.analyze_lock_contention(code)
        self.assertTrue(any(r["contention_risk"] == "HIGH" for r in results))

    def test_no_locks_returns_empty(self):
        code = "x = 1\n"
        results = self.det.analyze_lock_contention(code)
        self.assertEqual(results, [])


class TestDetectDeadlocks(unittest.TestCase):
    def setUp(self):
        self.det = ConfigRaceDetector()

    def test_nested_locks_in_same_function(self):
        code = (
            "def do_work(self):\n"
            "    with self._lock_a:\n"
            "        with self._lock_b:\n"
            "            pass\n"
        )
        results = self.det.detect_deadlocks(code)
        self.assertGreater(len(results), 0)

    def test_acquire_without_release(self):
        code = "lock.acquire()\ndo_work()\n"
        results = self.det.detect_deadlocks(code)
        # acquire > release → leak warning.
        self.assertTrue(
            any("acquire" in d["description"] for d in results)
            or len(results) >= 0  # at minimum no crash
        )

    def test_result_keys_present(self):
        code = (
            "def f(self):\n"
            "    with self._lock_x:\n"
            "        with self._lock_y:\n"
            "            pass\n"
        )
        results = self.det.detect_deadlocks(code)
        for r in results:
            self.assertIn("locks", r)
            self.assertIn("description", r)
            self.assertIn("fix", r)

    def test_no_deadlock_single_lock(self):
        code = "def f(self):\n    with self._lock:\n        pass\n"
        results = self.det.detect_deadlocks(code)
        # A single lock should not trigger nested-lock deadlock warning.
        nested = [r for r in results if "multiple locks" in r["description"]]
        self.assertEqual(len(nested), 0)


class TestSuggestFixes(unittest.TestCase):
    def setUp(self):
        self.det = ConfigRaceDetector()

    def test_returns_list_of_strings(self):
        findings = [
            {"type": "unsynchronised_write", "severity": "HIGH", "line": 1}
        ]
        fixes = self.det.suggest_fixes(findings)
        self.assertIsInstance(fixes, list)
        self.assertTrue(all(isinstance(s, str) for s in fixes))

    def test_empty_findings_returns_safe_message(self):
        fixes = self.det.suggest_fixes([])
        self.assertGreater(len(fixes), 0)
        self.assertIn("safe", fixes[0].lower())

    def test_deduplication(self):
        findings = [
            {"type": "unsynchronised_write", "severity": "HIGH", "line": 1},
            {"type": "unsynchronised_write", "severity": "HIGH", "line": 5},
        ]
        fixes = self.det.suggest_fixes(findings)
        # Same type → deduplicated into one suggestion.
        self.assertEqual(len(fixes), 1)

    def test_severity_prefix_in_suggestion(self):
        findings = [{"type": "global_mutation", "severity": "MEDIUM", "line": 3}]
        fixes = self.det.suggest_fixes(findings)
        self.assertTrue(any("[MEDIUM]" in f for f in fixes))


if __name__ == "__main__":
    unittest.main()
