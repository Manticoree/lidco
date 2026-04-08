"""Recipe Sharing — share automation recipes, workflow templates, best practices,
fork/customize, version (Task 1804)."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecipeStep:
    """A single step in an automation recipe."""

    name: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "action": self.action, "params": dict(self.params)}


@dataclass
class Recipe:
    """A shareable automation recipe."""

    name: str
    author: str
    description: str = ""
    version: str = "1.0.0"
    steps: list[RecipeStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    parent_id: str = ""  # fork source
    rating_sum: int = 0
    rating_count: int = 0
    downloads: int = 0
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()

    @property
    def recipe_id(self) -> str:
        """Deterministic ID based on name + version."""
        raw = f"{self.name}:{self.version}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @property
    def average_rating(self) -> float:
        if self.rating_count == 0:
            return 0.0
        return self.rating_sum / self.rating_count

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def is_fork(self) -> bool:
        return bool(self.parent_id)

    def rate(self, score: int) -> Recipe:
        """Return new recipe with rating added."""
        if not 1 <= score <= 5:
            raise ValueError(f"Rating must be 1-5, got {score}")
        return Recipe(
            name=self.name,
            author=self.author,
            description=self.description,
            version=self.version,
            steps=list(self.steps),
            tags=list(self.tags),
            parent_id=self.parent_id,
            rating_sum=self.rating_sum + score,
            rating_count=self.rating_count + 1,
            downloads=self.downloads,
            created_at=self.created_at,
        )

    def fork(self, new_author: str, new_name: str | None = None) -> Recipe:
        """Fork this recipe, preserving lineage."""
        return Recipe(
            name=new_name or f"{self.name}-fork",
            author=new_author,
            description=self.description,
            version="1.0.0",
            steps=[RecipeStep(s.name, s.action, dict(s.params)) for s in self.steps],
            tags=list(self.tags),
            parent_id=self.recipe_id,
            created_at=time.time(),
        )

    def bump_version(self, new_version: str) -> Recipe:
        """Return a new recipe with the version updated."""
        return Recipe(
            name=self.name,
            author=self.author,
            description=self.description,
            version=new_version,
            steps=list(self.steps),
            tags=list(self.tags),
            parent_id=self.parent_id,
            rating_sum=self.rating_sum,
            rating_count=self.rating_count,
            downloads=self.downloads,
            created_at=self.created_at,
        )

    def increment_downloads(self) -> Recipe:
        """Return new recipe with downloads incremented."""
        return Recipe(
            name=self.name,
            author=self.author,
            description=self.description,
            version=self.version,
            steps=list(self.steps),
            tags=list(self.tags),
            parent_id=self.parent_id,
            rating_sum=self.rating_sum,
            rating_count=self.rating_count,
            downloads=self.downloads + 1,
            created_at=self.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "author": self.author,
            "description": self.description,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "tags": list(self.tags),
            "parent_id": self.parent_id,
            "average_rating": self.average_rating,
            "downloads": self.downloads,
        }


class RecipeStore:
    """Community recipe store with sharing, forking, and versioning."""

    def __init__(self) -> None:
        self._recipes: dict[str, Recipe] = {}  # recipe_id -> Recipe

    @property
    def count(self) -> int:
        return len(self._recipes)

    def publish(self, recipe: Recipe) -> str:
        """Publish a recipe. Returns the recipe_id."""
        if not recipe.name:
            raise ValueError("Recipe name is required")
        rid = recipe.recipe_id
        self._recipes[rid] = recipe
        return rid

    def get(self, recipe_id: str) -> Recipe | None:
        return self._recipes.get(recipe_id)

    def remove(self, recipe_id: str) -> bool:
        if recipe_id in self._recipes:
            del self._recipes[recipe_id]
            return True
        return False

    def search(self, query: str) -> list[Recipe]:
        """Search recipes by name/description/tags."""
        q = query.lower()
        results: list[Recipe] = []
        for r in self._recipes.values():
            if (
                q in r.name.lower()
                or q in r.description.lower()
                or any(q in t.lower() for t in r.tags)
            ):
                results.append(r)
        return sorted(results, key=lambda x: x.downloads, reverse=True)

    def browse(self, limit: int = 50) -> list[Recipe]:
        """Browse published recipes sorted by downloads."""
        recipes = list(self._recipes.values())
        return sorted(recipes, key=lambda x: x.downloads, reverse=True)[:limit]

    def top_rated(self, limit: int = 10) -> list[Recipe]:
        """Top rated recipes."""
        rated = [r for r in self._recipes.values() if r.rating_count > 0]
        return sorted(rated, key=lambda x: x.average_rating, reverse=True)[:limit]

    def by_author(self, author: str) -> list[Recipe]:
        """Get all recipes by an author."""
        return [r for r in self._recipes.values() if r.author == author]

    def forks_of(self, recipe_id: str) -> list[Recipe]:
        """Get all forks of a given recipe."""
        return [r for r in self._recipes.values() if r.parent_id == recipe_id]

    def rate(self, recipe_id: str, score: int) -> bool:
        """Rate a recipe. Returns False if not found."""
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            return False
        self._recipes[recipe_id] = recipe.rate(score)
        return True

    def record_download(self, recipe_id: str) -> bool:
        """Increment download counter."""
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            return False
        self._recipes[recipe_id] = recipe.increment_downloads()
        return True

    def fork_recipe(self, recipe_id: str, new_author: str, new_name: str | None = None) -> str | None:
        """Fork a recipe, publish the fork, and return its ID."""
        original = self._recipes.get(recipe_id)
        if original is None:
            return None
        forked = original.fork(new_author, new_name)
        return self.publish(forked)

    def stats(self) -> dict[str, Any]:
        """Store statistics."""
        recipes = list(self._recipes.values())
        total_downloads = sum(r.downloads for r in recipes)
        total_forks = sum(1 for r in recipes if r.is_fork)
        authors: set[str] = {r.author for r in recipes}
        return {
            "total_recipes": len(recipes),
            "total_downloads": total_downloads,
            "total_forks": total_forks,
            "unique_authors": len(authors),
        }
