"""Shortcut trainer — quiz mode and progress tracking."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from lidco.shortcuts.registry import ShortcutRegistry


@dataclass
class TrainingProgress:
    """Progress for a single shortcut."""

    shortcut_keys: str
    attempts: int = 0
    correct: int = 0
    last_attempt: float = 0.0


@dataclass(frozen=True)
class QuizQuestion:
    """A quiz question asking the user for the shortcut keys."""

    command: str
    expected_keys: str
    hint: str = ""


class ShortcutTrainer:
    """Interactive shortcut learning with quiz mode."""

    def __init__(self, registry: ShortcutRegistry) -> None:
        self._registry = registry
        self._progress: dict[str, TrainingProgress] = {}

    def generate_quiz(self, count: int = 5) -> list[QuizQuestion]:
        shortcuts = [s for s in self._registry.all_shortcuts() if s.enabled]
        if not shortcuts:
            return []
        selected = random.sample(shortcuts, min(count, len(shortcuts)))
        return [
            QuizQuestion(
                command=s.command,
                expected_keys=s.keys,
                hint=s.description,
            )
            for s in selected
        ]

    def answer(self, command: str, keys: str) -> bool:
        """Check answer.  Returns True if *keys* matches the registered shortcut for *command*."""
        matches = self._registry.find_by_command(command)
        normalised = " ".join(keys.lower().split())
        correct = any(
            " ".join(m.keys.lower().split()) == normalised
            for m in matches
        )
        # update progress for the expected keys
        for m in matches:
            k = m.keys
            if k not in self._progress:
                self._progress[k] = TrainingProgress(shortcut_keys=k)
            p = self._progress[k]
            p.attempts += 1
            if correct:
                p.correct += 1
            p.last_attempt = time.time()
        return correct

    def progress(self, shortcut_keys: str | None = None) -> list[TrainingProgress]:
        if shortcut_keys is not None:
            p = self._progress.get(shortcut_keys)
            return [p] if p else []
        return list(self._progress.values())

    def accuracy(self) -> float:
        total_attempts = sum(p.attempts for p in self._progress.values())
        if total_attempts == 0:
            return 0.0
        total_correct = sum(p.correct for p in self._progress.values())
        return total_correct / total_attempts

    def weakest(self, limit: int = 5) -> list[TrainingProgress]:
        items = [p for p in self._progress.values() if p.attempts > 0]
        items.sort(key=lambda p: p.correct / max(p.attempts, 1))
        return items[:limit]

    def reset(self) -> None:
        self._progress.clear()

    def summary(self) -> dict:
        return {
            "total_shortcuts": len(self._progress),
            "total_attempts": sum(p.attempts for p in self._progress.values()),
            "total_correct": sum(p.correct for p in self._progress.values()),
            "accuracy": round(self.accuracy(), 4),
        }
