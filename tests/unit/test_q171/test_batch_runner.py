"""Tests for BatchRunner — Q171 task 969."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.api.batch_runner import BatchRunner, BatchJob
from lidco.api.library import LidcoResult


def _ok_exec(prompt: str) -> LidcoResult:
    return LidcoResult(success=True, output=f"ok:{prompt}", tokens_used=5, duration=0.01)


def _fail_exec(prompt: str) -> LidcoResult:
    return LidcoResult(success=False, output="", error="boom", tokens_used=0, duration=0.02)


class TestBatchJob(unittest.TestCase):
    def test_fields(self):
        j = BatchJob(prompt="hello", index=0)
        self.assertEqual(j.prompt, "hello")
        self.assertIsNone(j.result)


class TestLoadPrompts(unittest.TestCase):
    def test_plain_text(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("prompt one\nprompt two\n\nprompt three\n")
            path = f.name
        try:
            prompts = BatchRunner.load_prompts(path)
            self.assertEqual(prompts, ["prompt one", "prompt two", "prompt three"])
        finally:
            os.unlink(path)

    def test_json_array(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(["a", "b", "c"], f)
            path = f.name
        try:
            prompts = BatchRunner.load_prompts(path)
            self.assertEqual(prompts, ["a", "b", "c"])
        finally:
            os.unlink(path)

    def test_json_filters_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(["a", "", "  ", "b"], f)
            path = f.name
        try:
            prompts = BatchRunner.load_prompts(path)
            self.assertEqual(prompts, ["a", "b"])
        finally:
            os.unlink(path)


class TestRunSequential(unittest.TestCase):
    def test_success(self):
        runner = BatchRunner(execute_fn=_ok_exec)
        jobs = runner.run_sequential(["a", "b"])
        self.assertEqual(len(jobs), 2)
        self.assertTrue(jobs[0].result.success)
        self.assertEqual(jobs[0].index, 0)
        self.assertEqual(jobs[1].index, 1)

    def test_empty(self):
        runner = BatchRunner(execute_fn=_ok_exec)
        jobs = runner.run_sequential([])
        self.assertEqual(jobs, [])

    def test_run_all_delegates(self):
        runner = BatchRunner(execute_fn=_ok_exec)
        jobs = runner.run_all(["x"])
        self.assertEqual(len(jobs), 1)


class TestSummary(unittest.TestCase):
    def test_mixed(self):
        j1 = BatchJob(prompt="a", index=0, result=_ok_exec("a"))
        j2 = BatchJob(prompt="b", index=1, result=_fail_exec("b"))
        s = BatchRunner.summary([j1, j2])
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["success"], 1)
        self.assertEqual(s["fail"], 1)
        self.assertGreater(s["total_time"], 0)

    def test_all_success(self):
        jobs = [BatchJob(prompt="x", index=0, result=_ok_exec("x"))]
        s = BatchRunner.summary(jobs)
        self.assertEqual(s["success"], 1)
        self.assertEqual(s["fail"], 0)


class TestToJson(unittest.TestCase):
    def test_valid_json(self):
        j = BatchJob(prompt="hi", index=0, result=_ok_exec("hi"))
        raw = BatchRunner.to_json([j])
        data = json.loads(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["prompt"], "hi")
        self.assertTrue(data[0]["success"])

    def test_no_result(self):
        j = BatchJob(prompt="hi", index=0)
        raw = BatchRunner.to_json([j])
        data = json.loads(raw)
        self.assertNotIn("success", data[0])


if __name__ == "__main__":
    unittest.main()
