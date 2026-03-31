"""
Workflow Recipe Engine — chain conversation templates into multi-step
recipes with step dependencies and resume-on-failure support.

Stdlib only — no external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RecipeError(Exception):
    """Raised on recipe execution errors."""


class StepFailedError(RecipeError):
    """Raised when a recipe step fails."""


class DependencyError(RecipeError):
    """Raised when step dependencies cannot be resolved."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StepStatus(Enum):
    """Status of a recipe step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RecipeStatus(Enum):
    """Status of a recipe execution."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecipeStep:
    """A single step in a recipe."""

    name: str
    template_name: str  # References a ConversationTemplate by name
    variables: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    condition: str | None = None  # Optional condition
    on_failure: str = "stop"  # "stop", "skip", "retry"
    max_retries: int = 1
    timeout: float = 0.0  # 0 means no timeout


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_name: str
    status: StepStatus
    output: str = ""
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    retries: int = 0

    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0


@dataclass(frozen=True)
class Recipe:
    """A complete recipe definition."""

    name: str
    description: str = ""
    steps: tuple[RecipeStep, ...] = ()
    tags: tuple[str, ...] = ()
    version: str = "1.0"

    def step_names(self) -> list[str]:
        """Return list of step names in order."""
        return [s.name for s in self.steps]

    def get_step(self, name: str) -> RecipeStep | None:
        """Get step by name."""
        for s in self.steps:
            if s.name == name:
                return s
        return None


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

def resolve_execution_order(steps: tuple[RecipeStep, ...]) -> list[str]:
    """Topological sort of steps by dependencies.

    Returns step names in execution order.
    Raises DependencyError on circular dependencies.
    """
    name_set = {s.name for s in steps}
    deps: dict[str, set[str]] = {}
    for s in steps:
        for d in s.depends_on:
            if d not in name_set:
                raise DependencyError(f"Step '{s.name}' depends on unknown step '{d}'")
        deps[s.name] = set(s.depends_on)

    result: list[str] = []
    visited: set[str] = set()
    in_progress: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in in_progress:
            raise DependencyError(f"Circular dependency involving step '{name}'")
        in_progress.add(name)
        for d in deps.get(name, set()):
            visit(d)
        in_progress.discard(name)
        visited.add(name)
        result.append(name)

    for s in steps:
        visit(s.name)

    return result


# ---------------------------------------------------------------------------
# Recipe Engine
# ---------------------------------------------------------------------------

class RecipeEngine:
    """Execute multi-step recipes with dependency resolution and resume support."""

    def __init__(self) -> None:
        self._recipes: dict[str, Recipe] = {}
        self._results: dict[str, dict[str, StepResult]] = {}
        self._status: dict[str, RecipeStatus] = {}
        self._step_handler: Callable[[RecipeStep, dict[str, Any]], str] | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_step_handler(
        self,
        handler: Callable[[RecipeStep, dict[str, Any]], str],
    ) -> None:
        """Set the callback that executes each step.

        The handler receives (step, merged_variables) and returns output text.
        """
        self._step_handler = handler

    # ------------------------------------------------------------------
    # Recipe management
    # ------------------------------------------------------------------

    def register(self, recipe: Recipe) -> None:
        """Register a recipe."""
        self._recipes[recipe.name] = recipe

    def get(self, name: str) -> Recipe | None:
        """Get a registered recipe by name."""
        return self._recipes.get(name)

    def list_recipes(self) -> list[Recipe]:
        """List all registered recipes."""
        return list(self._recipes.values())

    def unregister(self, name: str) -> bool:
        """Remove a registered recipe. Returns True if found."""
        return self._recipes.pop(name, None) is not None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        recipe_name: str,
        variables: dict[str, Any] | None = None,
    ) -> list[StepResult]:
        """Execute a recipe end-to-end.

        Returns list of StepResult for each step executed.
        """
        recipe = self._recipes.get(recipe_name)
        if recipe is None:
            raise RecipeError(f"Recipe '{recipe_name}' not found")

        variables = dict(variables or {})
        order = resolve_execution_order(recipe.steps)
        self._status[recipe_name] = RecipeStatus.RUNNING
        results: dict[str, StepResult] = {}

        for step_name in order:
            step = recipe.get_step(step_name)
            if step is None:
                continue

            result = self._execute_step(step, variables, results)
            results[step_name] = result

            if result.status == StepStatus.FAILED and step.on_failure == "stop":
                self._status[recipe_name] = RecipeStatus.FAILED
                self._results[recipe_name] = results
                return list(results.values())

        self._status[recipe_name] = RecipeStatus.COMPLETED
        self._results[recipe_name] = results
        return list(results.values())

    def resume(
        self,
        recipe_name: str,
        variables: dict[str, Any] | None = None,
    ) -> list[StepResult]:
        """Resume a failed recipe from the last failed step."""
        recipe = self._recipes.get(recipe_name)
        if recipe is None:
            raise RecipeError(f"Recipe '{recipe_name}' not found")

        variables = dict(variables or {})
        previous = self._results.get(recipe_name, {})
        order = resolve_execution_order(recipe.steps)
        self._status[recipe_name] = RecipeStatus.RUNNING
        results: dict[str, StepResult] = dict(previous)

        for step_name in order:
            # Skip already completed steps
            prev = previous.get(step_name)
            if prev and prev.status == StepStatus.COMPLETED:
                continue

            step = recipe.get_step(step_name)
            if step is None:
                continue

            result = self._execute_step(step, variables, results)
            results[step_name] = result

            if result.status == StepStatus.FAILED and step.on_failure == "stop":
                self._status[recipe_name] = RecipeStatus.FAILED
                self._results[recipe_name] = results
                return list(results.values())

        self._status[recipe_name] = RecipeStatus.COMPLETED
        self._results[recipe_name] = results
        return list(results.values())

    def get_status(self, recipe_name: str) -> RecipeStatus:
        """Get the status of a recipe execution."""
        return self._status.get(recipe_name, RecipeStatus.IDLE)

    def get_results(self, recipe_name: str) -> list[StepResult]:
        """Get results for a recipe execution."""
        results = self._results.get(recipe_name, {})
        return list(results.values())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: RecipeStep,
        variables: dict[str, Any],
        prior_results: dict[str, StepResult],
    ) -> StepResult:
        """Execute a single step with retry support."""
        # Check dependencies
        for dep in step.depends_on:
            dep_result = prior_results.get(dep)
            if not dep_result or dep_result.status != StepStatus.COMPLETED:
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    error=f"Dependency '{dep}' not completed",
                )

        # Check condition
        if step.condition:
            from lidco.templates.conversation import _eval_condition
            if not _eval_condition(step.condition, variables):
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    error="Condition not met",
                )

        # Merge variables
        merged = {**variables, **step.variables}
        # Inject prior step outputs
        for name, res in prior_results.items():
            if res.status == StepStatus.COMPLETED:
                merged[f"step_{name}_output"] = res.output

        # Execute with retries
        retries = 0
        last_error = ""
        started_at = time.time()

        while retries <= step.max_retries:
            try:
                if self._step_handler:
                    output = self._step_handler(step, merged)
                else:
                    output = f"[Step '{step.name}' executed with template '{step.template_name}']"

                return StepResult(
                    step_name=step.name,
                    status=StepStatus.COMPLETED,
                    output=output,
                    started_at=started_at,
                    completed_at=time.time(),
                    retries=retries,
                )
            except Exception as exc:
                last_error = str(exc)
                retries += 1
                if step.on_failure == "skip":
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.SKIPPED,
                        error=last_error,
                        started_at=started_at,
                        completed_at=time.time(),
                        retries=retries,
                    )

        return StepResult(
            step_name=step.name,
            status=StepStatus.FAILED,
            error=last_error,
            started_at=started_at,
            completed_at=time.time(),
            retries=retries - 1,
        )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    """Serialize recipe to a dict."""
    return {
        "name": recipe.name,
        "description": recipe.description,
        "version": recipe.version,
        "tags": list(recipe.tags),
        "steps": [
            {
                "name": s.name,
                "template_name": s.template_name,
                "variables": dict(s.variables),
                "depends_on": list(s.depends_on),
                "condition": s.condition,
                "on_failure": s.on_failure,
                "max_retries": s.max_retries,
                "timeout": s.timeout,
            }
            for s in recipe.steps
        ],
    }


def recipe_from_dict(data: dict[str, Any]) -> Recipe:
    """Deserialize recipe from a dict."""
    steps = tuple(
        RecipeStep(
            name=s["name"],
            template_name=s["template_name"],
            variables=s.get("variables", {}),
            depends_on=tuple(s.get("depends_on", [])),
            condition=s.get("condition"),
            on_failure=s.get("on_failure", "stop"),
            max_retries=s.get("max_retries", 1),
            timeout=s.get("timeout", 0.0),
        )
        for s in data.get("steps", [])
    )
    return Recipe(
        name=data["name"],
        description=data.get("description", ""),
        steps=steps,
        tags=tuple(data.get("tags", [])),
        version=data.get("version", "1.0"),
    )
