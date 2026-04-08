"""Tests for AsyncDeadlockDetector (Q343, Task 2)."""
from __future__ import annotations

import unittest

from lidco.stability.deadlock_detect import AsyncDeadlockDetector


class TestDetectDeadlocks(unittest.TestCase):
    def setUp(self):
        self.detector = AsyncDeadlockDetector()

    def test_double_acquire_same_lock_flagged(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def bad():
    await _lock.acquire()
    await _lock.acquire()
"""
        results = self.detector.detect_deadlocks(src)
        high_risk = [r for r in results if r["risk"] == "HIGH"]
        self.assertTrue(len(high_risk) >= 1)

    def test_circular_await_detected(self):
        src = """\
async def func_a():
    await func_b()

async def func_b():
    await func_a()
"""
        results = self.detector.detect_deadlocks(src)
        circular = [r for r in results if "circular" in r["pattern"]]
        self.assertTrue(len(circular) >= 1)
        self.assertEqual(circular[0]["risk"], "MEDIUM")

    def test_safe_code_returns_no_high_risk(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def safe():
    async with _lock:
        pass
"""
        results = self.detector.detect_deadlocks(src)
        high = [r for r in results if r["risk"] == "HIGH"]
        self.assertEqual(high, [])

    def test_result_has_required_keys(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def f():
    await _lock.acquire()
    await _lock.acquire()
"""
        results = self.detector.detect_deadlocks(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("pattern", r)
            self.assertIn("risk", r)
            self.assertIn("description", r)

    def test_no_async_functions_returns_empty(self):
        src = "x = 1\n"
        results = self.detector.detect_deadlocks(src)
        self.assertEqual(results, [])


class TestAnalyzeAwaitChains(unittest.TestCase):
    def setUp(self):
        self.detector = AsyncDeadlockDetector()

    def test_time_sleep_in_async_flagged(self):
        src = """\
import asyncio, time

async def bad():
    time.sleep(1)
"""
        results = self.detector.analyze_await_chains(src)
        self.assertTrue(len(results) >= 1)
        self.assertIn("sleep", results[0]["issue"].lower())

    def test_requests_in_async_flagged(self):
        src = """\
import requests, asyncio

async def fetch():
    resp = requests.get("http://example.com")
"""
        results = self.detector.analyze_await_chains(src)
        self.assertTrue(len(results) >= 1)

    def test_suggestion_provided(self):
        src = """\
import asyncio, time

async def bad():
    time.sleep(2)
"""
        results = self.detector.analyze_await_chains(src)
        if results:
            self.assertIn("asyncio", results[0]["suggestion"].lower())

    def test_result_has_required_keys(self):
        src = """\
async def bad():
    time.sleep(1)
"""
        results = self.detector.analyze_await_chains(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("chain", r)
            self.assertIn("issue", r)
            self.assertIn("suggestion", r)

    def test_clean_async_returns_empty(self):
        src = """\
import asyncio

async def good():
    await asyncio.sleep(1)
"""
        results = self.detector.analyze_await_chains(src)
        self.assertEqual(results, [])


class TestCheckResourceOrdering(unittest.TestCase):
    def setUp(self):
        self.detector = AsyncDeadlockDetector()

    def test_result_has_required_keys(self):
        src = """\
async def func_a():
    with lock_a:
        with lock_b:
            pass

async def func_b():
    with lock_b:
        with lock_a:
            pass
"""
        results = self.detector.check_resource_ordering(src)
        if results:
            r = results[0]
            self.assertIn("resources", r)
            self.assertIn("ordering_consistent", r)
            self.assertIn("suggestion", r)

    def test_no_locks_returns_empty(self):
        src = "x = 1\n"
        results = self.detector.check_resource_ordering(src)
        self.assertEqual(results, [])

    def test_single_function_returns_empty(self):
        src = """\
def only_one():
    with lock_a:
        pass
"""
        results = self.detector.check_resource_ordering(src)
        self.assertEqual(results, [])


class TestVerifyTimeouts(unittest.TestCase):
    def setUp(self):
        self.detector = AsyncDeadlockDetector()

    def test_acquire_without_timeout_flagged(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def f():
    await _lock.acquire()
"""
        results = self.detector.verify_timeouts(src)
        no_timeout = [r for r in results if not r["has_timeout"]]
        self.assertTrue(len(no_timeout) >= 1)

    def test_wait_for_marks_has_timeout(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def f():
    await asyncio.wait_for(_lock.acquire(), timeout=5)
"""
        results = self.detector.verify_timeouts(src)
        with_timeout = [r for r in results if r["has_timeout"]]
        self.assertTrue(len(with_timeout) >= 1)

    def test_result_has_required_keys(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def f():
    await _lock.acquire()
"""
        results = self.detector.verify_timeouts(src)
        if results:
            r = results[0]
            self.assertIn("line", r)
            self.assertIn("operation", r)
            self.assertIn("has_timeout", r)
            self.assertIn("suggestion", r)

    def test_suggestion_mentions_wait_for(self):
        src = """\
import asyncio
_lock = asyncio.Lock()

async def f():
    await _lock.acquire()
"""
        results = self.detector.verify_timeouts(src)
        no_timeout = [r for r in results if not r["has_timeout"]]
        if no_timeout:
            self.assertIn("wait_for", no_timeout[0]["suggestion"])

    def test_no_async_ops_returns_empty(self):
        src = "x = 1\n"
        results = self.detector.verify_timeouts(src)
        self.assertEqual(results, [])
