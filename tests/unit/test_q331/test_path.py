"""Tests for lidco.learning.path -- LearningPath, LearningPathGenerator."""
from __future__ import annotations

import unittest

from lidco.learning.path import (
    LearningPath,
    LearningPathGenerator,
    PathStep,
    Resource,
)


class TestResource(unittest.TestCase):
    def test_defaults(self) -> None:
        r = Resource(title="Docs")
        self.assertEqual(r.kind, "article")
        self.assertEqual(r.estimated_minutes, 30)


class TestPathStep(unittest.TestCase):
    def test_complete_returns_new(self) -> None:
        step = PathStep(title="Step 1", skill="python")
        completed = step.complete()
        self.assertFalse(step.completed)
        self.assertTrue(completed.completed)
        self.assertEqual(completed.title, "Step 1")


class TestLearningPath(unittest.TestCase):
    def test_progress_empty(self) -> None:
        path = LearningPath(name="test")
        self.assertEqual(path.progress, 0.0)

    def test_progress_partial(self) -> None:
        path = LearningPath(name="test")
        path.add_step(PathStep(title="a", skill="x"))
        path.add_step(PathStep(title="b", skill="y"))
        path.complete_step(0)
        self.assertAlmostEqual(path.progress, 0.5)

    def test_completed_count(self) -> None:
        path = LearningPath(name="test")
        path.add_step(PathStep(title="a", skill="x"))
        path.add_step(PathStep(title="b", skill="y"))
        path.complete_step(0)
        self.assertEqual(path.completed_count, 1)

    def test_next_step(self) -> None:
        path = LearningPath(name="test")
        path.add_step(PathStep(title="a", skill="x"))
        path.add_step(PathStep(title="b", skill="y"))
        path.complete_step(0)
        nxt = path.next_step()
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.title, "b")

    def test_next_step_all_done(self) -> None:
        path = LearningPath(name="test")
        path.add_step(PathStep(title="a", skill="x"))
        path.complete_step(0)
        self.assertIsNone(path.next_step())

    def test_complete_step_invalid_index(self) -> None:
        path = LearningPath(name="test")
        path.add_step(PathStep(title="a", skill="x"))
        path.complete_step(99)  # no error
        self.assertEqual(path.completed_count, 0)


class TestLearningPathGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = LearningPathGenerator()

    def test_generate_default_steps(self) -> None:
        path = self.gen.generate(["python", "rust"])
        self.assertEqual(len(path.steps), 2)
        self.assertIn("python", path.target_skills)
        self.assertIn("rust", path.target_skills)

    def test_generate_with_template(self) -> None:
        self.gen.register_template("python", [
            {"title": "Basics", "description": "Learn basics"},
            {"title": "Advanced", "description": "Go deeper"},
        ])
        path = self.gen.generate(["python"])
        self.assertEqual(len(path.steps), 2)
        self.assertEqual(path.steps[0].title, "Basics")

    def test_generate_with_project_needs(self) -> None:
        path = self.gen.generate(["python"], project_needs=["docker"])
        self.assertIn("docker", path.target_skills)
        self.assertEqual(len(path.steps), 2)

    def test_generate_template_with_resources(self) -> None:
        self.gen.register_template("go", [
            {
                "title": "Go basics",
                "resources": [{"title": "Tour of Go", "url": "https://go.dev/tour", "kind": "tutorial"}],
            }
        ])
        path = self.gen.generate(["go"])
        self.assertEqual(len(path.steps[0].resources), 1)
        self.assertEqual(path.steps[0].resources[0].kind, "tutorial")

    def test_format_path_empty(self) -> None:
        path = LearningPath(name="empty")
        result = self.gen.format_path(path)
        self.assertIn("no steps", result)

    def test_format_path_with_steps(self) -> None:
        path = self.gen.generate(["python"])
        result = self.gen.format_path(path)
        self.assertIn("python", result)
        self.assertIn("[ ]", result)

    def test_format_path_completed(self) -> None:
        path = self.gen.generate(["python"])
        path.complete_step(0)
        result = self.gen.format_path(path)
        self.assertIn("[x]", result)


if __name__ == "__main__":
    unittest.main()
