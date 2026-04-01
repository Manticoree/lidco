"""Tests for feature_dev.explorer — CodeExplorerAgent and data classes."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.feature_dev.explorer import (
    ArchitectureMap,
    CodeExplorerAgent,
    ExecutionFlow,
    ExplorationResult,
    SimilarFeature,
)


class TestExplorationResult(unittest.TestCase):
    def test_frozen(self):
        r = ExplorationResult(root="/x", files_found=3, focus_hits=("a",), summary="ok")
        with self.assertRaises(AttributeError):
            r.root = "/y"  # type: ignore[misc]

    def test_fields(self):
        r = ExplorationResult(root="/tmp", files_found=10, focus_hits=("a", "b"), summary="done")
        self.assertEqual(r.root, "/tmp")
        self.assertEqual(r.files_found, 10)
        self.assertEqual(r.focus_hits, ("a", "b"))
        self.assertEqual(r.summary, "done")


class TestExecutionFlow(unittest.TestCase):
    def test_frozen(self):
        f = ExecutionFlow(entry_point="main.py", steps=("def foo",), calls=("bar",))
        with self.assertRaises(AttributeError):
            f.entry_point = "x"  # type: ignore[misc]

    def test_fields(self):
        f = ExecutionFlow(entry_point="app.py", steps=(), calls=())
        self.assertEqual(f.entry_point, "app.py")
        self.assertEqual(f.steps, ())
        self.assertEqual(f.calls, ())


class TestArchitectureMap(unittest.TestCase):
    def test_frozen(self):
        m = ArchitectureMap(root="/r", modules=("a",), dependencies=("b",), summary="ok")
        with self.assertRaises(AttributeError):
            m.root = "/s"  # type: ignore[misc]

    def test_fields(self):
        m = ArchitectureMap(root="/r", modules=("core", "cli"), dependencies=("click",), summary="2 mods")
        self.assertEqual(m.modules, ("core", "cli"))
        self.assertEqual(m.dependencies, ("click",))


class TestSimilarFeature(unittest.TestCase):
    def test_frozen(self):
        s = SimilarFeature(name="cache", path="/x/cache", similarity=0.8, description="match")
        with self.assertRaises(AttributeError):
            s.name = "other"  # type: ignore[misc]

    def test_fields(self):
        s = SimilarFeature(name="auth", path="/p/auth", similarity=0.5, description="partial")
        self.assertEqual(s.name, "auth")
        self.assertAlmostEqual(s.similarity, 0.5)


class TestCodeExplorerExplore(unittest.TestCase):
    def test_nonexistent_path(self):
        agent = CodeExplorerAgent()
        result = agent.explore("/nonexistent/path/xyz")
        self.assertEqual(result.files_found, 0)
        self.assertIn("not a directory", result.summary)

    def test_explore_real_directory(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "foo.py"), "w").close()
            open(os.path.join(td, "bar.txt"), "w").close()
            result = agent_explore(td)
            self.assertEqual(result.files_found, 2)
            self.assertEqual(result.root, td)

    def test_focus_areas(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "cache.py"), "w").close()
            open(os.path.join(td, "auth.py"), "w").close()
            open(os.path.join(td, "utils.py"), "w").close()
            agent = CodeExplorerAgent()
            result = agent.explore(td, ("cache",))
            self.assertEqual(len(result.focus_hits), 1)
            self.assertIn("cache.py", result.focus_hits[0])

    def test_empty_focus(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "a.py"), "w").close()
            agent = CodeExplorerAgent()
            result = agent.explore(td, ())
            self.assertEqual(len(result.focus_hits), 0)


class TestCodeExplorerTrace(unittest.TestCase):
    def test_nonexistent_file(self):
        agent = CodeExplorerAgent()
        flow = agent.trace_execution("/no/such/file.py")
        self.assertEqual(flow.steps, ())
        self.assertEqual(flow.calls, ())

    def test_trace_real_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    print('hi')\n\nclass Foo:\n    pass\n")
            f.flush()
            path = f.name
        try:
            agent = CodeExplorerAgent()
            flow = agent.trace_execution(path)
            self.assertEqual(flow.entry_point, path)
            # split("(")[0] keeps "def hello" and "class Foo:"
            self.assertTrue(any("def hello" in s for s in flow.steps))
            self.assertTrue(any("class Foo" in s for s in flow.steps))
        finally:
            os.unlink(path)


class TestCodeExplorerArchMap(unittest.TestCase):
    def test_nonexistent_path(self):
        agent = CodeExplorerAgent()
        result = agent.map_architecture("/nonexistent/xyz")
        self.assertEqual(result.modules, ())
        self.assertIn("not a directory", result.summary)

    def test_real_directory(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "core"))
            os.makedirs(os.path.join(td, "cli"))
            agent = CodeExplorerAgent()
            result = agent.map_architecture(td)
            self.assertIn("cli", result.modules)
            self.assertIn("core", result.modules)

    def test_requirements_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "requirements.txt"), "w") as f:
                f.write("click>=8.0\nrich==13.0\n# comment\n")
            agent = CodeExplorerAgent()
            result = agent.map_architecture(td)
            self.assertIn("click", result.dependencies)
            self.assertIn("rich", result.dependencies)


class TestCodeExplorerSimilar(unittest.TestCase):
    def test_nonexistent_path(self):
        agent = CodeExplorerAgent()
        result = agent.find_similar_features("cache system", "/nonexistent/xyz")
        self.assertEqual(result, ())

    def test_find_matching_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "cache"))
            os.makedirs(os.path.join(td, "auth"))
            os.makedirs(os.path.join(td, "utils"))
            agent = CodeExplorerAgent()
            result = agent.find_similar_features("cache layer", td)
            self.assertGreaterEqual(len(result), 1)
            self.assertEqual(result[0].name, "cache")

    def test_empty_description(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "core"))
            agent = CodeExplorerAgent()
            result = agent.find_similar_features("", td)
            self.assertEqual(result, ())


def agent_explore(td: str) -> ExplorationResult:
    """Helper to explore with default agent."""
    return CodeExplorerAgent().explore(td)


if __name__ == "__main__":
    unittest.main()
