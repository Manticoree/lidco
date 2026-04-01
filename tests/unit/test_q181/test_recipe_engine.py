"""Tests for RecipeEngine, Recipe, and helpers."""
from __future__ import annotations

import unittest

from lidco.templates.recipe_engine import (
    DependencyError,
    Recipe,
    RecipeEngine,
    RecipeError,
    RecipeStatus,
    RecipeStep,
    StepResult,
    StepStatus,
    recipe_from_dict,
    recipe_to_dict,
    resolve_execution_order,
)


def _two_step_recipe() -> Recipe:
    return Recipe(
        name="build",
        description="Build pipeline",
        steps=(
            RecipeStep(name="compile", template_name="compile_tmpl"),
            RecipeStep(name="test", template_name="test_tmpl", depends_on=("compile",)),
        ),
        tags=("ci",),
    )


class TestRecipeStep(unittest.TestCase):
    def test_frozen(self):
        s = RecipeStep(name="a", template_name="t")
        with self.assertRaises(AttributeError):
            s.name = "b"  # type: ignore[misc]


class TestRecipe(unittest.TestCase):
    def test_step_names(self):
        r = _two_step_recipe()
        self.assertEqual(r.step_names(), ["compile", "test"])

    def test_get_step(self):
        r = _two_step_recipe()
        self.assertIsNotNone(r.get_step("compile"))
        self.assertIsNone(r.get_step("missing"))


class TestResolveExecutionOrder(unittest.TestCase):
    def test_simple_order(self):
        steps = _two_step_recipe().steps
        order = resolve_execution_order(steps)
        self.assertEqual(order, ["compile", "test"])

    def test_circular_dependency(self):
        steps = (
            RecipeStep(name="a", template_name="t", depends_on=("b",)),
            RecipeStep(name="b", template_name="t", depends_on=("a",)),
        )
        with self.assertRaises(DependencyError):
            resolve_execution_order(steps)

    def test_unknown_dependency(self):
        steps = (
            RecipeStep(name="a", template_name="t", depends_on=("nonexistent",)),
        )
        with self.assertRaises(DependencyError):
            resolve_execution_order(steps)


class TestRecipeEngine(unittest.TestCase):
    def test_register_and_list(self):
        engine = RecipeEngine()
        r = _two_step_recipe()
        engine.register(r)
        self.assertEqual(len(engine.list_recipes()), 1)
        self.assertIsNotNone(engine.get("build"))

    def test_execute_default_handler(self):
        engine = RecipeEngine()
        engine.register(_two_step_recipe())
        results = engine.execute("build")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == StepStatus.COMPLETED for r in results))
        self.assertEqual(engine.get_status("build"), RecipeStatus.COMPLETED)

    def test_execute_custom_handler(self):
        engine = RecipeEngine()
        engine.register(_two_step_recipe())
        outputs: list[str] = []

        def handler(step, variables):
            outputs.append(step.name)
            return f"done:{step.name}"

        engine.set_step_handler(handler)
        results = engine.execute("build")
        self.assertEqual(outputs, ["compile", "test"])
        self.assertEqual(results[0].output, "done:compile")

    def test_execute_handler_failure_stops(self):
        engine = RecipeEngine()
        engine.register(Recipe(
            name="fail",
            steps=(
                RecipeStep(name="bad", template_name="t", max_retries=0, on_failure="stop"),
            ),
        ))
        engine.set_step_handler(lambda s, v: (_ for _ in ()).throw(RuntimeError("boom")))
        results = engine.execute("fail")
        self.assertEqual(results[0].status, StepStatus.FAILED)
        self.assertEqual(engine.get_status("fail"), RecipeStatus.FAILED)

    def test_resume_skips_completed(self):
        engine = RecipeEngine()
        fail_always = True

        def handler(step, variables):
            nonlocal fail_always
            if step.name == "test" and fail_always:
                raise RuntimeError("flaky")
            return "ok"

        # Use max_retries=0 so test step fails immediately
        recipe = Recipe(
            name="build",
            description="Build pipeline",
            steps=(
                RecipeStep(name="compile", template_name="compile_tmpl"),
                RecipeStep(name="test", template_name="test_tmpl",
                           depends_on=("compile",), max_retries=0, on_failure="stop"),
            ),
        )
        engine.register(recipe)
        engine.set_step_handler(handler)
        # First run: compile passes, test fails
        engine.execute("build")
        self.assertEqual(engine.get_status("build"), RecipeStatus.FAILED)

        # Resume: should skip compile, retry test (now succeeds)
        fail_always = False
        results = engine.resume("build")
        completed = [r for r in results if r.status == StepStatus.COMPLETED]
        self.assertEqual(len(completed), 2)

    def test_execute_not_found(self):
        engine = RecipeEngine()
        with self.assertRaises(RecipeError):
            engine.execute("nope")


class TestRecipeSerialization(unittest.TestCase):
    def test_round_trip(self):
        r = _two_step_recipe()
        data = recipe_to_dict(r)
        restored = recipe_from_dict(data)
        self.assertEqual(restored.name, r.name)
        self.assertEqual(len(restored.steps), len(r.steps))
        self.assertEqual(restored.steps[1].depends_on, ("compile",))

    def test_step_result_duration(self):
        sr = StepResult(step_name="x", status=StepStatus.COMPLETED, started_at=1.0, completed_at=3.5)
        self.assertAlmostEqual(sr.duration, 2.5)


if __name__ == "__main__":
    unittest.main()
