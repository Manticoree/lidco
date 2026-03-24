"""ArenaMode — run the same task through multiple models and compare."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ArenaEntry:
    model: str
    output: str
    duration: float
    token_count: int
    score: float = 0.0


@dataclass
class ArenaResult:
    task: str
    entries: list[ArenaEntry]
    winner: ArenaEntry | None  # None until selected
    selection_method: str  # "human" | "auto_score" | "auto_test"


class ArenaMode:
    """Run a task on multiple models and compare/select the best output."""

    DEFAULT_MODELS = ["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514"]

    def __init__(self, models: list[str] | None = None) -> None:
        self._models = models if models is not None else list(self.DEFAULT_MODELS)
        self._history: list[ArenaResult] = []

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
        model_fn: Callable[[str, str], tuple[str, int]] | None = None,
    ) -> ArenaResult:
        """Run task through each model and return ArenaResult(winner=None).

        model_fn(model_name, task) -> (output, token_count)
        """
        entries: list[ArenaEntry] = []

        for model in self._models:
            start = time.monotonic()
            if model_fn is None:
                output = f"[stub output for {model}]"
                token_count = len(output.split())
            else:
                try:
                    output, token_count = model_fn(model, task)
                except Exception as exc:
                    output = f"[error: {exc}]"
                    token_count = 0
            duration = time.monotonic() - start

            entries.append(ArenaEntry(
                model=model,
                output=output,
                duration=duration,
                token_count=token_count,
                score=0.0,
            ))

        result = ArenaResult(
            task=task,
            entries=entries,
            winner=None,
            selection_method="",
        )
        self._history = [*self._history, result]
        return result

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_winner(self, result: ArenaResult, index: int) -> ArenaResult:
        """Return a NEW ArenaResult with winner=entries[index], method="human"."""
        winner = result.entries[index]
        new_result = ArenaResult(
            task=result.task,
            entries=list(result.entries),
            winner=winner,
            selection_method="human",
        )
        # Update the matching history entry
        self._history = [
            new_result if r is result else r
            for r in self._history
        ]
        return new_result

    def auto_select(
        self,
        result: ArenaResult,
        test_fn: Callable[[str], bool] | None = None,
    ) -> ArenaResult:
        """Select winner automatically.

        If test_fn provided: prefer passing candidates; among passing pick highest score,
        then tiebreak on longest output.
        Otherwise: pick highest score.
        Returns new ArenaResult (does not mutate result).
        """
        entries = result.entries
        if not entries:
            new_result = ArenaResult(
                task=result.task,
                entries=[],
                winner=None,
                selection_method="auto_score",
            )
            self._history = [
                new_result if r is result else r
                for r in self._history
            ]
            return new_result

        if test_fn is not None:
            passing = [e for e in entries if test_fn(e.output)]
            pool = passing if passing else entries
            method = "auto_test"
        else:
            pool = entries
            method = "auto_score"

        winner = max(pool, key=lambda e: (e.score, len(e.output)))

        new_result = ArenaResult(
            task=result.task,
            entries=list(entries),
            winner=winner,
            selection_method=method,
        )
        self._history = [
            new_result if r is result else r
            for r in self._history
        ]
        return new_result

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def format_comparison(self, result: ArenaResult) -> str:
        """Return a Markdown table comparing all entries."""
        header = "| Model | Tokens | Duration | Score | Output |\n"
        separator = "|-------|--------|----------|-------|--------|\n"
        rows = []
        for entry in result.entries:
            preview = entry.output[:80].replace("|", "\\|")
            rows.append(
                f"| {entry.model} | {entry.token_count} "
                f"| {entry.duration:.3f}s | {entry.score:.2f} | {preview} |"
            )
        return header + separator + "\n".join(rows)

    # ------------------------------------------------------------------
    # History & stats
    # ------------------------------------------------------------------

    def history(self) -> list[ArenaResult]:
        """Return a copy of the history list."""
        return list(self._history)

    def win_rates(self) -> dict[str, float]:
        """Return model → (wins / appearances) from history.

        Only counts results where winner is set.
        """
        wins: dict[str, int] = {}
        appearances: dict[str, int] = {}

        for result in self._history:
            if result.winner is None:
                continue
            for entry in result.entries:
                appearances[entry.model] = appearances.get(entry.model, 0) + 1
            wins[result.winner.model] = wins.get(result.winner.model, 0) + 1

        rates: dict[str, float] = {}
        for model, count in appearances.items():
            rates[model] = wins.get(model, 0) / count if count > 0 else 0.0
        return rates
