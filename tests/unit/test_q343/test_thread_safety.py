"""Tests for ThreadSafetyAnalyzer (Q343, Task 1)."""
from __future__ import annotations

import unittest

from lidco.stability.thread_safety import ThreadSafetyAnalyzer


class TestFindUnguardedState(unittest.TestCase):
    def setUp(self):
        self.analyzer = ThreadSafetyAnalyzer()

    def test_module_level_dict_mutation_flagged(self):
        src = """\
_cache = {}

def add_item(key, value):
    _cache[key] = value
"""
        results = self.analyzer.find_unguarded_state(src)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["variable"], "_cache")

    def test_module_level_list_append_flagged(self):
        src = """\
_items = []

def add(item):
    _items.append(item)
"""
        results = self.analyzer.find_unguarded_state(src)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["variable"], "_items")

    def test_guarded_mutation_not_flagged(self):
        src = """\
import threading
_cache = {}
_lock = threading.Lock()

def add_item(key, value):
    with _lock:
        _cache[key] = value
"""
        results = self.analyzer.find_unguarded_state(src)
        self.assertEqual(results, [])

    def test_result_has_required_keys(self):
        src = """\
_store = {}

def put(k, v):
    _store[k] = v
"""
        results = self.analyzer.find_unguarded_state(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("variable", r)
            self.assertIn("issue", r)
            self.assertIn("suggestion", r)

    def test_suggestion_mentions_lock(self):
        src = """\
_data = []

def store(x):
    _data.append(x)
"""
        results = self.analyzer.find_unguarded_state(src)
        if results:
            self.assertIn("lock", results[0]["suggestion"].lower())

    def test_no_mutations_returns_empty(self):
        src = "x = 1\ny = x + 2\n"
        results = self.analyzer.find_unguarded_state(src)
        self.assertEqual(results, [])


class TestAnalyzeLocks(unittest.TestCase):
    def setUp(self):
        self.analyzer = ThreadSafetyAnalyzer()

    def test_context_manager_usage_detected(self):
        src = """\
import threading
_lock = threading.Lock()

def safe():
    with _lock:
        pass
"""
        results = self.analyzer.analyze_locks(src)
        cm_results = [r for r in results if r["usage"] == "context_manager"]
        self.assertTrue(len(cm_results) >= 1)
        self.assertEqual(cm_results[0]["issues"], [])

    def test_manual_acquire_flagged(self):
        src = """\
import threading
_lock = threading.Lock()

def unsafe():
    _lock.acquire()
    do_work()
"""
        results = self.analyzer.analyze_locks(src)
        manual = [r for r in results if r["usage"] == "manual_acquire"]
        self.assertTrue(len(manual) >= 1)
        self.assertTrue(len(manual[0]["issues"]) > 0)

    def test_anonymous_lock_flagged(self):
        src = """\
import threading

def func():
    with threading.Lock():
        pass
"""
        results = self.analyzer.analyze_locks(src)
        anon = [r for r in results if r["usage"] == "anonymous_lock"]
        self.assertTrue(len(anon) >= 1)

    def test_result_has_required_keys(self):
        src = """\
import threading
_lock = threading.RLock()

def f():
    with _lock:
        pass
"""
        results = self.analyzer.analyze_locks(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("lock_type", r)
            self.assertIn("usage", r)
            self.assertIn("issues", r)

    def test_no_locks_returns_empty(self):
        src = "x = 1\n"
        results = self.analyzer.analyze_locks(src)
        self.assertEqual(results, [])


class TestAuditAtomicOps(unittest.TestCase):
    def setUp(self):
        self.analyzer = ThreadSafetyAnalyzer()

    def test_augmented_assign_flagged(self):
        src = "counter += 1\n"
        results = self.analyzer.audit_atomic_ops(src)
        self.assertTrue(len(results) >= 1)
        self.assertFalse(results[0]["atomic"])

    def test_locked_operation_marked_atomic(self):
        src = """\
import threading
_lock = threading.Lock()

def inc():
    with _lock:
        counter += 1
"""
        results = self.analyzer.audit_atomic_ops(src)
        locked_ops = [r for r in results if r["atomic"]]
        self.assertTrue(len(locked_ops) >= 1)

    def test_result_has_required_keys(self):
        src = "x += 1\n"
        results = self.analyzer.audit_atomic_ops(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("operation", r)
            self.assertIn("atomic", r)
            self.assertIn("suggestion", r)

    def test_suggestion_mentions_lock_for_non_atomic(self):
        src = "total -= 5\n"
        results = self.analyzer.audit_atomic_ops(src)
        if results:
            self.assertIn("lock", results[0]["suggestion"].lower())


class TestVerifyThreadLocal(unittest.TestCase):
    def setUp(self):
        self.analyzer = ThreadSafetyAnalyzer()

    def test_threading_local_detected_as_good(self):
        src = """\
import threading
_local = threading.local()
"""
        results = self.analyzer.verify_thread_local(src)
        tl = [r for r in results if r["uses_thread_local"]]
        self.assertTrue(len(tl) >= 1)

    def test_manual_thread_keyed_dict_flagged(self):
        src = """\
import threading
_thread_data = {}
_thread_data[threading.get_ident()] = "value"
"""
        results = self.analyzer.verify_thread_local(src)
        flagged = [r for r in results if not r["uses_thread_local"]]
        self.assertTrue(len(flagged) >= 1)

    def test_result_has_required_keys(self):
        src = "import threading\n_local = threading.local()\n"
        results = self.analyzer.verify_thread_local(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("pattern", r)
            self.assertIn("uses_thread_local", r)
            self.assertIn("suggestion", r)

    def test_no_thread_patterns_returns_empty(self):
        src = "x = 1\n"
        results = self.analyzer.verify_thread_local(src)
        self.assertEqual(results, [])
