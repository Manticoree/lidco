"""Tests for TestIsolationEnforcer (Q341 Task 1)."""
from __future__ import annotations

import unittest


class TestFindSharedState(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_isolation import TestIsolationEnforcer
        self.e = TestIsolationEnforcer()

    def test_empty_source_returns_empty(self):
        result = self.e.find_shared_state("")
        self.assertEqual(result, [])

    def test_module_level_list_detected(self):
        source = "SHARED = []\n"
        result = self.e.find_shared_state(source)
        self.assertTrue(any(r["variable"] == "SHARED" for r in result))

    def test_module_level_dict_detected(self):
        source = "STATE = {}\n"
        result = self.e.find_shared_state(source)
        self.assertTrue(any(r["variable"] == "STATE" for r in result))

    def test_module_level_list_is_high_risk(self):
        source = "CACHE = []\n"
        result = self.e.find_shared_state(source)
        item = next(r for r in result if r["variable"] == "CACHE")
        self.assertEqual(item["risk"], "HIGH")

    def test_class_level_mutable_detected(self):
        source = (
            "class MyTest:\n"
            "    shared_data = {}\n"
        )
        result = self.e.find_shared_state(source)
        self.assertTrue(any(r["variable"] == "shared_data" for r in result))

    def test_class_level_type_is_class_variable(self):
        source = (
            "class MyTest:\n"
            "    items = []\n"
        )
        result = self.e.find_shared_state(source)
        item = next(r for r in result if r["variable"] == "items")
        self.assertEqual(item["type"], "class_variable")

    def test_module_level_integer_not_flagged(self):
        source = "COUNT = 5\n"
        result = self.e.find_shared_state(source)
        self.assertFalse(any(r["variable"] == "COUNT" for r in result))

    def test_module_level_string_not_flagged(self):
        source = 'NAME = "test"\n'
        result = self.e.find_shared_state(source)
        self.assertEqual(result, [])

    def test_line_number_reported_correctly(self):
        source = "\n\nSHARED = []\n"
        result = self.e.find_shared_state(source)
        self.assertEqual(result[0]["line"], 3)


class TestFindGlobalMutations(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_isolation import TestIsolationEnforcer
        self.e = TestIsolationEnforcer()

    def test_empty_source_returns_empty(self):
        self.assertEqual(self.e.find_global_mutations(""), [])

    def test_os_environ_assignment_detected(self):
        source = "os.environ['KEY'] = 'val'\n"
        result = self.e.find_global_mutations(source)
        self.assertTrue(len(result) > 0)

    def test_sys_path_append_detected(self):
        source = "sys.path.append('/tmp')\n"
        result = self.e.find_global_mutations(source)
        self.assertTrue(len(result) > 0)

    def test_global_keyword_detected(self):
        source = (
            "def test_something():\n"
            "    global counter\n"
            "    counter += 1\n"
        )
        result = self.e.find_global_mutations(source)
        self.assertTrue(any(r["mutation_type"] == "global_keyword" for r in result))

    def test_global_keyword_suggestion_mentions_variable(self):
        source = (
            "def f():\n"
            "    global my_var\n"
        )
        result = self.e.find_global_mutations(source)
        item = next(r for r in result if r["mutation_type"] == "global_keyword")
        self.assertIn("my_var", item["suggestion"])

    def test_env_mutation_type_for_environ(self):
        source = "os.environ['X'] = '1'\n"
        result = self.e.find_global_mutations(source)
        self.assertTrue(any(r["mutation_type"] == "env_mutation" for r in result))

    def test_sys_path_mutation_type(self):
        source = "sys.path.append('.')\n"
        result = self.e.find_global_mutations(source)
        self.assertTrue(any(r["mutation_type"] == "sys_path_mutation" for r in result))


class TestDetectFixtureLeaks(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_isolation import TestIsolationEnforcer
        self.e = TestIsolationEnforcer()

    def test_clean_fixture_with_yield_and_teardown_no_finding(self):
        source = (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def db():\n"
            "    conn = connect()\n"
            "    yield conn\n"
            "    conn.close()\n"
        )
        result = self.e.detect_fixture_leaks(source)
        self.assertEqual(result, [])

    def test_fixture_opens_resource_no_yield_flagged(self):
        source = (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def db():\n"
            "    conn = open('file.txt')\n"
            "    return conn\n"
        )
        result = self.e.detect_fixture_leaks(source)
        self.assertTrue(any(r["fixture_name"] == "db" for r in result))

    def test_fixture_yield_no_teardown_flagged(self):
        source = (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def my_fix():\n"
            "    yield 42\n"
        )
        result = self.e.detect_fixture_leaks(source)
        self.assertTrue(any(r["fixture_name"] == "my_fix" for r in result))

    def test_non_fixture_function_not_flagged(self):
        source = (
            "def helper():\n"
            "    f = open('x')\n"
            "    return f\n"
        )
        result = self.e.detect_fixture_leaks(source)
        self.assertEqual(result, [])


class TestVerifyCleanup(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_isolation import TestIsolationEnforcer
        self.e = TestIsolationEnforcer()

    def test_paired_setup_teardown_ok(self):
        source = (
            "class MyTest:\n"
            "    def setUp(self): pass\n"
            "    def tearDown(self): pass\n"
        )
        result = self.e.verify_cleanup(source)
        statuses = {r["method"]: r["status"] for r in result}
        self.assertEqual(statuses.get("setUp"), "ok")
        self.assertEqual(statuses.get("tearDown"), "ok")

    def test_setup_without_teardown_flagged(self):
        source = (
            "class MyTest:\n"
            "    def setUp(self): pass\n"
        )
        result = self.e.verify_cleanup(source)
        item = next(r for r in result if r["method"] == "setUp")
        self.assertEqual(item["status"], "missing_cleanup")

    def test_setup_class_without_teardown_class_flagged(self):
        source = (
            "class MyTest:\n"
            "    @classmethod\n"
            "    def setUpClass(cls): pass\n"
        )
        result = self.e.verify_cleanup(source)
        self.assertTrue(any(r["method"] == "setUpClass" for r in result))

    def test_empty_source_no_findings(self):
        result = self.e.verify_cleanup("")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
