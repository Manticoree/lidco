"""Spawn parallel exploration variants for a given task."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid


@dataclass
class ExplorationVariant:
    id: str
    prompt: str
    strategy: str  # "conservative", "aggressive", "balanced", "creative"
    status: str = "pending"  # "pending", "running", "completed", "failed", "cancelled"
    result: str | None = None
    diff: str | None = None
    score: float = 0.0
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None


@dataclass
class ExplorationConfig:
    max_variants: int = 3
    strategies: list[str] = field(default_factory=lambda: ["conservative", "balanced", "aggressive"])
    timeout: float = 300.0  # 5 minutes per variant


@dataclass
class Exploration:
    id: str
    original_prompt: str
    variants: list[ExplorationVariant]
    status: str = "pending"  # "pending", "running", "completed", "cancelled"
    winner_id: str | None = None
    created_at: float = field(default_factory=time.time)


class ExplorationSpawner:
    def __init__(self, config: ExplorationConfig | None = None):
        self._config = config or ExplorationConfig()
        self._explorations: dict[str, Exploration] = {}

    @property
    def config(self) -> ExplorationConfig:
        return self._config

    def create_exploration(self, prompt: str, num_variants: int | None = None) -> Exploration:
        """Create a new exploration with N variant prompts."""
        n = min(num_variants or self._config.max_variants, self._config.max_variants)
        strategies = self._config.strategies[:n]

        variants = []
        for strategy in strategies:
            variant_prompt = self._generate_variant_prompt(prompt, strategy)
            variants.append(ExplorationVariant(
                id=f"var_{uuid.uuid4().hex[:8]}",
                prompt=variant_prompt,
                strategy=strategy,
            ))

        exploration = Exploration(
            id=f"exp_{uuid.uuid4().hex[:8]}",
            original_prompt=prompt,
            variants=variants,
        )
        self._explorations = {**self._explorations, exploration.id: exploration}
        return exploration

    def _generate_variant_prompt(self, prompt: str, strategy: str) -> str:
        """Generate a variant prompt for the given strategy."""
        prefixes = {
            "conservative": "Take a minimal, safe approach with minimal changes: ",
            "balanced": "Take a balanced approach considering both simplicity and completeness: ",
            "aggressive": "Take a comprehensive approach, refactoring as needed for the best solution: ",
            "creative": "Think outside the box and consider unconventional approaches: ",
        }
        return prefixes.get(strategy, "") + prompt

    def start_variant(self, exploration_id: str, variant_id: str) -> Exploration:
        """Mark a variant as running. Returns updated exploration."""
        exp = self._explorations.get(exploration_id)
        if not exp:
            raise ValueError(f"Exploration not found: {exploration_id}")

        new_variants = []
        for v in exp.variants:
            if v.id == variant_id:
                new_variants.append(ExplorationVariant(
                    id=v.id, prompt=v.prompt, strategy=v.strategy,
                    status="running", started_at=time.time(),
                    result=v.result, diff=v.diff, score=v.score,
                    completed_at=v.completed_at, error=v.error,
                ))
            else:
                new_variants.append(v)

        updated = Exploration(
            id=exp.id, original_prompt=exp.original_prompt,
            variants=new_variants, status="running",
            winner_id=exp.winner_id, created_at=exp.created_at,
        )
        self._explorations = {**self._explorations, exp.id: updated}
        return updated

    def complete_variant(self, exploration_id: str, variant_id: str, result: str, diff: str = "") -> Exploration:
        """Mark a variant as completed with its result."""
        exp = self._explorations.get(exploration_id)
        if not exp:
            raise ValueError(f"Exploration not found: {exploration_id}")

        new_variants = []
        for v in exp.variants:
            if v.id == variant_id:
                new_variants.append(ExplorationVariant(
                    id=v.id, prompt=v.prompt, strategy=v.strategy,
                    status="completed", result=result, diff=diff,
                    started_at=v.started_at, completed_at=time.time(),
                    score=v.score, error=v.error,
                ))
            else:
                new_variants.append(v)

        # Check if all variants done
        all_done = all(v.status in ("completed", "failed", "cancelled") for v in new_variants)

        updated = Exploration(
            id=exp.id, original_prompt=exp.original_prompt,
            variants=new_variants,
            status="completed" if all_done else exp.status,
            winner_id=exp.winner_id, created_at=exp.created_at,
        )
        self._explorations = {**self._explorations, exp.id: updated}
        return updated

    def fail_variant(self, exploration_id: str, variant_id: str, error: str) -> Exploration:
        """Mark a variant as failed."""
        exp = self._explorations.get(exploration_id)
        if not exp:
            raise ValueError(f"Exploration not found: {exploration_id}")

        new_variants = []
        for v in exp.variants:
            if v.id == variant_id:
                new_variants.append(ExplorationVariant(
                    id=v.id, prompt=v.prompt, strategy=v.strategy,
                    status="failed", error=error,
                    started_at=v.started_at, completed_at=time.time(),
                    result=v.result, diff=v.diff, score=v.score,
                ))
            else:
                new_variants.append(v)

        all_done = all(v.status in ("completed", "failed", "cancelled") for v in new_variants)
        updated = Exploration(
            id=exp.id, original_prompt=exp.original_prompt,
            variants=new_variants,
            status="completed" if all_done else exp.status,
            winner_id=exp.winner_id, created_at=exp.created_at,
        )
        self._explorations = {**self._explorations, exp.id: updated}
        return updated

    def get_exploration(self, exploration_id: str) -> Exploration | None:
        return self._explorations.get(exploration_id)

    def list_explorations(self) -> list[Exploration]:
        return list(self._explorations.values())

    def cancel_exploration(self, exploration_id: str) -> Exploration:
        """Cancel all pending/running variants."""
        exp = self._explorations.get(exploration_id)
        if not exp:
            raise ValueError(f"Exploration not found: {exploration_id}")

        new_variants = []
        for v in exp.variants:
            if v.status in ("pending", "running"):
                new_variants.append(ExplorationVariant(
                    id=v.id, prompt=v.prompt, strategy=v.strategy,
                    status="cancelled", started_at=v.started_at,
                    completed_at=time.time(), result=v.result,
                    diff=v.diff, score=v.score, error=v.error,
                ))
            else:
                new_variants.append(v)

        updated = Exploration(
            id=exp.id, original_prompt=exp.original_prompt,
            variants=new_variants, status="cancelled",
            winner_id=exp.winner_id, created_at=exp.created_at,
        )
        self._explorations = {**self._explorations, exp.id: updated}
        return updated
