"""Tests for ResourceCleanupValidator (Q343, Task 4)."""
from __future__ import annotations

import unittest

from lidco.stability.resource_cleanup import ResourceCleanupValidator


class TestCheckFileHandles(unittest.TestCase):
    def setUp(self):
        self.validator = ResourceCleanupValidator()

    def test_assignment_without_cm_flagged(self):
        src = "f = open('test.txt', 'r')\n"
        results = self.validator.check_file_handles(src)
        self.assertTrue(len(results) >= 1)
        self.assertFalse(results[0]["uses_context_manager"])

    def test_with_open_is_ok(self):
        src = "with open('test.txt', 'r') as f:\n    data = f.read()\n"
        results = self.validator.check_file_handles(src)
        self.assertTrue(len(results) >= 1)
        self.assertTrue(results[0]["uses_context_manager"])

    def test_suggestion_mentions_context_manager(self):
        src = "f = open('data.csv')\n"
        results = self.validator.check_file_handles(src)
        if results and not results[0]["uses_context_manager"]:
            self.assertIn("with open", results[0]["suggestion"])

    def test_result_has_required_keys(self):
        src = "f = open('x.txt')\n"
        results = self.validator.check_file_handles(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("pattern", r)
            self.assertIn("uses_context_manager", r)
            self.assertIn("suggestion", r)

    def test_no_open_returns_empty(self):
        src = "x = 1\n"
        results = self.validator.check_file_handles(src)
        self.assertEqual(results, [])


class TestCheckConnections(unittest.TestCase):
    def setUp(self):
        self.validator = ResourceCleanupValidator()

    def test_sqlite_without_close_flagged(self):
        src = "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\n"
        results = self.validator.check_connections(src)
        self.assertTrue(len(results) >= 1)
        no_cleanup = [r for r in results if not r["has_cleanup"]]
        self.assertTrue(len(no_cleanup) >= 1)

    def test_sqlite_with_close_ok(self):
        src = """\
import sqlite3
conn = sqlite3.connect('db.sqlite3')
conn.close()
"""
        results = self.validator.check_connections(src)
        with_cleanup = [r for r in results if r["has_cleanup"]]
        self.assertTrue(len(with_cleanup) >= 1)

    def test_context_manager_usage_ok(self):
        src = """\
import sqlite3
with sqlite3.connect('db.sqlite3') as conn:
    conn.execute('SELECT 1')
"""
        results = self.validator.check_connections(src)
        with_cm = [r for r in results if r["has_cleanup"]]
        self.assertTrue(len(with_cm) >= 1)

    def test_result_has_required_keys(self):
        src = "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\n"
        results = self.validator.check_connections(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("connection_type", r)
            self.assertIn("has_cleanup", r)
            self.assertIn("suggestion", r)

    def test_no_connections_returns_empty(self):
        src = "x = 1\n"
        results = self.validator.check_connections(src)
        self.assertEqual(results, [])

    def test_connection_type_identified(self):
        src = "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\n"
        results = self.validator.check_connections(src)
        if results:
            self.assertEqual(results[0]["connection_type"], "sqlite3")


class TestCheckTempDirs(unittest.TestCase):
    def setUp(self):
        self.validator = ResourceCleanupValidator()

    def test_mkdtemp_without_cleanup_flagged(self):
        src = "import tempfile\ntmpdir = tempfile.mkdtemp()\n"
        results = self.validator.check_temp_dirs(src)
        self.assertTrue(len(results) >= 1)
        self.assertFalse(results[0]["has_cleanup"])

    def test_temporary_directory_as_context_manager_ok(self):
        src = """\
import tempfile
with tempfile.TemporaryDirectory() as d:
    pass
"""
        results = self.validator.check_temp_dirs(src)
        self.assertTrue(len(results) >= 1)
        self.assertTrue(results[0]["has_cleanup"])

    def test_mkdtemp_with_rmtree_ok(self):
        src = """\
import tempfile, shutil
tmpdir = tempfile.mkdtemp()
shutil.rmtree(tmpdir)
"""
        results = self.validator.check_temp_dirs(src)
        with_cleanup = [r for r in results if r["has_cleanup"]]
        self.assertTrue(len(with_cleanup) >= 1)

    def test_result_has_required_keys(self):
        src = "import tempfile\ntmpdir = tempfile.mkdtemp()\n"
        results = self.validator.check_temp_dirs(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("pattern", r)
            self.assertIn("has_cleanup", r)
            self.assertIn("suggestion", r)

    def test_no_temp_patterns_returns_empty(self):
        src = "x = 1\n"
        results = self.validator.check_temp_dirs(src)
        self.assertEqual(results, [])


class TestAuditDelMethods(unittest.TestCase):
    def setUp(self):
        self.validator = ResourceCleanupValidator()

    def test_del_calling_self_method_flagged(self):
        src = """\
class MyClass:
    def __del__(self):
        self.close()
"""
        results = self.validator.audit_del_methods(src)
        self.assertTrue(len(results) >= 1)
        self.assertTrue(len(results[0]["issues"]) > 0)

    def test_del_with_raise_flagged(self):
        src = """\
class MyClass:
    def __del__(self):
        raise RuntimeError("error in del")
"""
        results = self.validator.audit_del_methods(src)
        self.assertTrue(len(results) >= 1)
        issues_text = " ".join(results[0]["issues"])
        self.assertIn("raise", issues_text.lower())

    def test_class_name_captured(self):
        src = """\
class Connector:
    def __del__(self):
        self.disconnect()
"""
        results = self.validator.audit_del_methods(src)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["class_name"], "Connector")

    def test_result_has_required_keys(self):
        src = """\
class A:
    def __del__(self):
        pass
"""
        results = self.validator.audit_del_methods(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("class_name", r)
            self.assertIn("issues", r)
            self.assertIn("suggestion", r)

    def test_no_del_method_returns_empty(self):
        src = """\
class A:
    def close(self):
        pass
"""
        results = self.validator.audit_del_methods(src)
        self.assertEqual(results, [])

    def test_suggestion_non_empty_when_issues(self):
        src = """\
class B:
    def __del__(self):
        self.cleanup()
"""
        results = self.validator.audit_del_methods(src)
        if results and results[0]["issues"]:
            self.assertTrue(len(results[0]["suggestion"]) > 0)
