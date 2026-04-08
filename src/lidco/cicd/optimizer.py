"""
Pipeline Optimizer — reduce build time via selective testing,
artifact caching, and skip-unchanged logic.

Operates on a ``PipelineAnalysis`` (from analyzer) and produces
concrete optimisation recommendations plus a rewritten config.
Pure stdlib.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Optimization:
    """A single optimisation recommendation."""

    kind: str  # "cache", "skip", "parallel", "selective-test", "artifact"
    stage: str
    description: str
    estimated_savings: float  # seconds saved


@dataclass(frozen=True)
class OptimizationResult:
    """Full optimisation report."""

    optimizations: list[Optimization]
    total_estimated_savings: float
    original_duration: float
    optimized_duration: float
    skip_unchanged_paths: list[str]


class PipelineOptimizer:
    """Optimize CI/CD pipeline configuration."""

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        stages: list[dict[str, Any]],
        *,
        enable_cache: bool = True,
        enable_skip: bool = True,
        enable_selective: bool = True,
    ) -> OptimizationResult:
        """Analyze *stages* and return optimisation suggestions.

        Each stage dict has keys: ``name``, ``steps`` (list[str]),
        ``has_cache`` (bool), ``depends_on`` (list[str]),
        ``estimated_duration`` (float).
        """
        optimizations: list[Optimization] = []
        skip_paths: list[str] = []

        for s in stages:
            name = s.get("name", "unknown")
            dur = s.get("estimated_duration", 60.0)

            if enable_cache and not s.get("has_cache", False):
                saving = dur * 0.3
                optimizations.append(
                    Optimization(
                        kind="cache",
                        stage=name,
                        description=f"Add dependency caching to '{name}'",
                        estimated_savings=saving,
                    )
                )

            if enable_skip:
                paths = self._detect_skip_paths(s)
                if paths:
                    skip_paths.extend(paths)
                    optimizations.append(
                        Optimization(
                            kind="skip",
                            stage=name,
                            description=f"Skip '{name}' when {', '.join(paths)} unchanged",
                            estimated_savings=dur * 0.5,
                        )
                    )

            if enable_selective and self._can_selective_test(s):
                optimizations.append(
                    Optimization(
                        kind="selective-test",
                        stage=name,
                        description=f"Run only affected tests in '{name}'",
                        estimated_savings=dur * 0.4,
                    )
                )

        # Parallel opportunities
        independent = [s for s in stages if not s.get("depends_on")]
        if len(independent) > 1:
            names = [s.get("name", "?") for s in independent]
            total_dur = sum(s.get("estimated_duration", 60.0) for s in independent)
            max_dur = max(s.get("estimated_duration", 60.0) for s in independent)
            optimizations.append(
                Optimization(
                    kind="parallel",
                    stage=", ".join(names),
                    description=f"Run {', '.join(names)} in parallel",
                    estimated_savings=total_dur - max_dur,
                )
            )

        total_savings = sum(o.estimated_savings for o in optimizations)
        original = sum(s.get("estimated_duration", 60.0) for s in stages)
        optimized = max(0.0, original - total_savings)

        return OptimizationResult(
            optimizations=optimizations,
            total_estimated_savings=total_savings,
            original_duration=original,
            optimized_duration=optimized,
            skip_unchanged_paths=skip_paths,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def compute_path_hash(self, path: str) -> str:
        """Compute content hash of a file for change detection."""
        full = os.path.join(self._repo_path, path)
        if not os.path.isfile(full):
            return ""
        h = hashlib.sha256()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _detect_skip_paths(stage: dict[str, Any]) -> list[str]:
        """Return paths that, if unchanged, allow skipping this stage."""
        steps = stage.get("steps", [])
        paths: list[str] = []
        for step in steps:
            if not isinstance(step, str):
                continue
            lower = step.lower()
            if "test" in lower:
                paths.append("tests/")
            if "lint" in lower:
                paths.append("src/")
            if "build" in lower:
                paths.append("src/")
            if "docs" in lower or "doc" in lower:
                paths.append("docs/")
        return list(dict.fromkeys(paths))  # dedupe, preserve order

    @staticmethod
    def _can_selective_test(stage: dict[str, Any]) -> bool:
        """Return True if stage appears to run tests."""
        steps = stage.get("steps", [])
        return any(
            isinstance(s, str) and ("test" in s.lower() or "pytest" in s.lower())
            for s in steps
        )
