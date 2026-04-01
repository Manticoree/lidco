"""Code Architect Agent — propose and evaluate architecture for features.

All data classes are frozen (immutable).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureProposal:
    """A single architecture proposal."""

    name: str
    description: str
    trade_offs: tuple[str, ...]
    complexity_score: float  # 0.0 = trivial, 1.0 = very complex


@dataclass(frozen=True)
class Blueprint:
    """Detailed implementation blueprint derived from a proposal."""

    components: tuple[str, ...]
    dependencies: tuple[str, ...]
    files_to_create: tuple[str, ...]
    files_to_modify: tuple[str, ...]
    steps: tuple[str, ...]


class ArchitectError(Exception):
    """Raised when architecture generation fails."""


class CodeArchitectAgent:
    """Generate and evaluate architecture proposals.

    This is a lightweight stub; real implementations would integrate
    with an LLM to produce richer proposals.
    """

    def __init__(self, *, max_proposals: int = 3) -> None:
        self._max_proposals = max_proposals

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def propose(
        self,
        requirements: str,
        patterns: tuple[str, ...] = (),
    ) -> tuple[ArchitectureProposal, ...]:
        """Generate up to *max_proposals* architecture proposals.

        Proposals are ranked by complexity score (lowest first).
        """
        if not requirements.strip():
            raise ArchitectError("Requirements must not be empty")

        proposals: list[ArchitectureProposal] = []
        base_patterns = patterns or ("modular", "layered", "event-driven")

        for i, pattern in enumerate(base_patterns[: self._max_proposals]):
            score = round(0.2 + (i * 0.25), 2)
            proposals.append(ArchitectureProposal(
                name=f"{pattern}-approach",
                description=(
                    f"Implement '{requirements[:60]}' using {pattern} pattern"
                ),
                trade_offs=(
                    f"Pro: {pattern} is well-understood",
                    f"Con: {pattern} adds indirection",
                ),
                complexity_score=score,
            ))

        return tuple(sorted(proposals, key=lambda p: p.complexity_score))

    def recommend(
        self,
        proposals: tuple[ArchitectureProposal, ...],
    ) -> ArchitectureProposal:
        """Pick the best proposal (lowest complexity that is non-trivial)."""
        if not proposals:
            raise ArchitectError("No proposals to evaluate")

        # Prefer mid-range complexity: not too trivial, not too complex.
        scored = sorted(
            proposals,
            key=lambda p: abs(p.complexity_score - 0.4),
        )
        return scored[0]

    def generate_blueprint(
        self,
        proposal: ArchitectureProposal,
    ) -> Blueprint:
        """Expand a proposal into an actionable blueprint."""
        name_slug = proposal.name.replace(" ", "_").replace("-", "_")
        return Blueprint(
            components=(
                f"{name_slug}_core",
                f"{name_slug}_api",
                f"{name_slug}_tests",
            ),
            dependencies=("typing", "dataclasses"),
            files_to_create=(
                f"src/{name_slug}/core.py",
                f"src/{name_slug}/api.py",
            ),
            files_to_modify=(
                "src/registry.py",
            ),
            steps=(
                f"1. Create {name_slug} package",
                f"2. Implement core logic ({name_slug}_core)",
                f"3. Wire API surface ({name_slug}_api)",
                "4. Register in main registry",
                "5. Add tests and verify coverage",
            ),
        )


__all__ = [
    "ArchitectureProposal",
    "Blueprint",
    "ArchitectError",
    "CodeArchitectAgent",
]
