"""Tests for Python Library API — Q171 task 968."""
from __future__ import annotations

import unittest

from lidco.api import library
from lidco.api.library import LidcoResult


class TestLidcoResult(unittest.TestCase):
    def test_defaults(self):
        r = LidcoResult(success=True, output="ok")
        self.assertTrue(r.success)
        self.assertEqual(r.output, "ok")
        self.assertEqual(r.files_changed, [])
        self.assertEqual(r.tokens_used, 0)
        self.assertEqual(r.error, "")

    def test_failure(self):
        r = LidcoResult(success=False, output="", error="boom")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "boom")


class TestLibraryRun(unittest.TestCase):
    def setUp(self):
        self._orig = library._execute_fn

    def tearDown(self):
        library._execute_fn = self._orig

    def _set_exec(self, fn):
        library.set_execute_fn(fn)

    def test_run_success(self):
        self._set_exec(lambda prompt, **kw: {"output": "hello", "tokens_used": 10})
        r = library.run("say hello")
        self.assertTrue(r.success)
        self.assertEqual(r.output, "hello")
        self.assertEqual(r.tokens_used, 10)

    def test_run_error(self):
        self._set_exec(lambda prompt, **kw: {"output": "", "error": "fail"})
        r = library.run("bad")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "fail")

    def test_run_exception(self):
        def _boom(prompt, **kw):
            raise RuntimeError("crash")
        self._set_exec(_boom)
        r = library.run("x")
        self.assertFalse(r.success)
        self.assertIn("crash", r.error)

    def test_run_duration(self):
        self._set_exec(lambda prompt, **kw: {"output": "ok"})
        r = library.run("x")
        self.assertGreaterEqual(r.duration, 0)

    def test_run_files_changed(self):
        self._set_exec(lambda prompt, **kw: {"output": "ok", "files_changed": ["a.py"]})
        r = library.run("x")
        self.assertEqual(r.files_changed, ["a.py"])


class TestLibraryEdit(unittest.TestCase):
    def setUp(self):
        self._orig = library._execute_fn

    def tearDown(self):
        library._execute_fn = self._orig

    def test_edit_passes_args(self):
        calls = []
        def _exec(prompt, **kw):
            calls.append((prompt, kw))
            return {"output": "edited"}
        library.set_execute_fn(_exec)
        r = library.edit("foo.py", "fix bug", dry_run=True)
        self.assertTrue(r.success)
        self.assertEqual(len(calls), 1)
        self.assertIn("foo.py", calls[0][0])
        self.assertTrue(calls[0][1]["dry_run"])


class TestLibraryAsk(unittest.TestCase):
    def setUp(self):
        self._orig = library._execute_fn

    def tearDown(self):
        library._execute_fn = self._orig

    def test_ask_with_context(self):
        library.set_execute_fn(lambda prompt, **kw: {"output": "42"})
        r = library.ask("what is 6*7", context="math")
        self.assertTrue(r.success)
        self.assertEqual(r.output, "42")

    def test_ask_without_context(self):
        library.set_execute_fn(lambda prompt, **kw: {"output": "yes"})
        r = library.ask("hello?")
        self.assertTrue(r.success)


class TestLibraryReview(unittest.TestCase):
    def setUp(self):
        self._orig = library._execute_fn

    def tearDown(self):
        library._execute_fn = self._orig

    def test_review(self):
        library.set_execute_fn(lambda prompt, **kw: {"output": "looks good"})
        r = library.review("main.py")
        self.assertTrue(r.success)
        self.assertIn("looks good", r.output)


class TestDefaultExecutor(unittest.TestCase):
    def test_default_returns_error(self):
        library.set_execute_fn(library._default_execute)
        r = library.run("anything")
        self.assertFalse(r.success)
        self.assertIn("no executor", r.error)


if __name__ == "__main__":
    unittest.main()
