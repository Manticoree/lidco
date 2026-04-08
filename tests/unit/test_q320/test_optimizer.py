"""Tests for cicd.optimizer module."""

import os
import tempfile
import unittest
from unittest.mock import patch

from lidco.cicd.optimizer import (
    Optimization,
    OptimizationResult,
    PipelineOptimizer,
)


class TestOptimization(unittest.TestCase):
    def test_frozen(self):
        o = Optimization(kind="cache", stage="x", description="d", estimated_savings=10.0)
        with self.assertRaises(AttributeError):
            o.kind = "y"  # type: ignore[misc]


class TestOptimizationResult(unittest.TestCase):
    def test_frozen(self):
        r = OptimizationResult(
            optimizations=[],
            total_estimated_savings=0.0,
            original_duration=0.0,
            optimized_duration=0.0,
            skip_unchanged_paths=[],
        )
        with self.assertRaises(AttributeError):
            r.original_duration = 1.0  # type: ignore[misc]


class TestPipelineOptimizer(unittest.TestCase):
    def _make_stages(self):
        return [
            {
                "name": "lint",
                "steps": ["ruff check ."],
                "has_cache": False,
                "depends_on": [],
                "estimated_duration": 30.0,
            },
            {
                "name": "test",
                "steps": ["pip install", "pytest tests/"],
                "has_cache": False,
                "depends_on": [],
                "estimated_duration": 120.0,
            },
            {
                "name": "build",
                "steps": ["python -m build"],
                "has_cache": True,
                "depends_on": ["lint", "test"],
                "estimated_duration": 60.0,
            },
        ]

    def test_optimize_basic(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages())
        self.assertIsInstance(result, OptimizationResult)
        self.assertGreater(result.total_estimated_savings, 0)
        self.assertGreater(result.original_duration, result.optimized_duration)

    def test_cache_suggestions(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages())
        cache_opts = [o for o in result.optimizations if o.kind == "cache"]
        # lint and test have no cache
        self.assertTrue(len(cache_opts) >= 1)

    def test_selective_test_suggestion(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages())
        sel = [o for o in result.optimizations if o.kind == "selective-test"]
        self.assertTrue(len(sel) >= 1)
        self.assertEqual(sel[0].stage, "test")

    def test_parallel_suggestion(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages())
        par = [o for o in result.optimizations if o.kind == "parallel"]
        self.assertEqual(len(par), 1)
        self.assertIn("lint", par[0].stage)
        self.assertIn("test", par[0].stage)

    def test_skip_paths(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages())
        self.assertTrue(len(result.skip_unchanged_paths) > 0)

    def test_disable_cache(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages(), enable_cache=False)
        cache_opts = [o for o in result.optimizations if o.kind == "cache"]
        self.assertEqual(len(cache_opts), 0)

    def test_disable_skip(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages(), enable_skip=False)
        skip_opts = [o for o in result.optimizations if o.kind == "skip"]
        self.assertEqual(len(skip_opts), 0)
        self.assertEqual(result.skip_unchanged_paths, [])

    def test_disable_selective(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(self._make_stages(), enable_selective=False)
        sel = [o for o in result.optimizations if o.kind == "selective-test"]
        self.assertEqual(len(sel), 0)

    def test_no_parallel_single_independent(self):
        stages = [
            {
                "name": "test",
                "steps": ["pytest"],
                "has_cache": True,
                "depends_on": [],
                "estimated_duration": 60.0,
            },
            {
                "name": "build",
                "steps": ["make"],
                "has_cache": True,
                "depends_on": ["test"],
                "estimated_duration": 30.0,
            },
        ]
        opt = PipelineOptimizer("/fake")
        result = opt.optimize(stages)
        par = [o for o in result.optimizations if o.kind == "parallel"]
        self.assertEqual(len(par), 0)

    def test_empty_stages(self):
        opt = PipelineOptimizer("/fake")
        result = opt.optimize([])
        self.assertEqual(result.total_estimated_savings, 0.0)
        self.assertEqual(result.original_duration, 0.0)


class TestPathHash(unittest.TestCase):
    def test_hash_existing_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello world")
            path = f.name
        try:
            opt = PipelineOptimizer(os.path.dirname(path))
            h = opt.compute_path_hash(os.path.basename(path))
            self.assertEqual(len(h), 64)  # sha256 hex
        finally:
            os.unlink(path)

    def test_hash_missing_file(self):
        opt = PipelineOptimizer("/fake")
        h = opt.compute_path_hash("nonexistent.txt")
        self.assertEqual(h, "")


class TestDetectSkipPaths(unittest.TestCase):
    def test_test_step(self):
        paths = PipelineOptimizer._detect_skip_paths({"steps": ["pytest tests/"]})
        self.assertIn("tests/", paths)

    def test_lint_step(self):
        paths = PipelineOptimizer._detect_skip_paths({"steps": ["ruff lint src/"]})
        self.assertIn("src/", paths)

    def test_docs_step(self):
        paths = PipelineOptimizer._detect_skip_paths({"steps": ["build docs"]})
        self.assertIn("docs/", paths)

    def test_no_steps(self):
        paths = PipelineOptimizer._detect_skip_paths({"steps": []})
        self.assertEqual(paths, [])

    def test_dedup(self):
        paths = PipelineOptimizer._detect_skip_paths(
            {"steps": ["lint src/", "build src/"]}
        )
        self.assertEqual(paths.count("src/"), 1)


if __name__ == "__main__":
    unittest.main()
