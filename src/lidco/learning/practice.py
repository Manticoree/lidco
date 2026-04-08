"""Practice Generator -- coding exercises from codebase patterns, difficulty scaling, auto-grading."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Exercise:
    """A coding exercise."""

    exercise_id: str
    title: str
    description: str
    difficulty: int = 1  # 1-5
    skill: str = ""
    hints: list[str] = field(default_factory=list)
    solution: str = ""
    template: str = ""  # starter code

    def hint(self, index: int = 0) -> str:
        if 0 <= index < len(self.hints):
            return self.hints[index]
        return "No hint available."


@dataclass
class Submission:
    """A user submission for an exercise."""

    exercise_id: str
    code: str
    timestamp: float = 0.0
    passed: bool = False
    score: float = 0.0  # 0.0-1.0
    feedback: str = ""


GraderFunc = Callable[[str, str], tuple[bool, float, str]]
"""(user_code, solution) -> (passed, score, feedback)"""


def default_grader(user_code: str, solution: str) -> tuple[bool, float, str]:
    """Simple equality grader with whitespace normalization."""
    normalized_user = user_code.strip()
    normalized_sol = solution.strip()
    if normalized_user == normalized_sol:
        return True, 1.0, "Perfect match!"
    # partial credit: check if key lines present
    sol_lines = set(normalized_sol.splitlines())
    user_lines = set(normalized_user.splitlines())
    if not sol_lines:
        return False, 0.0, "No solution to compare."
    overlap = len(sol_lines & user_lines)
    score = overlap / len(sol_lines)
    passed = score >= 0.8
    feedback = f"Matched {overlap}/{len(sol_lines)} lines."
    if passed:
        feedback += " Good enough!"
    else:
        feedback += " Keep trying."
    return passed, score, feedback


class PracticeGenerator:
    """Generate and manage coding exercises."""

    def __init__(self, grader: GraderFunc | None = None) -> None:
        self._exercises: dict[str, Exercise] = {}
        self._submissions: list[Submission] = []
        self._grader: GraderFunc = grader or default_grader

    def add_exercise(self, exercise: Exercise) -> None:
        self._exercises[exercise.exercise_id] = exercise

    def generate_from_pattern(
        self,
        pattern_name: str,
        code_snippet: str,
        difficulty: int = 1,
        skill: str = "",
    ) -> Exercise:
        eid = hashlib.md5(f"{pattern_name}:{code_snippet[:50]}".encode()).hexdigest()[:8]
        exercise = Exercise(
            exercise_id=eid,
            title=f"Practice: {pattern_name}",
            description=f"Implement the '{pattern_name}' pattern.",
            difficulty=max(1, min(5, difficulty)),
            skill=skill or pattern_name,
            template=f"# Implement {pattern_name} here\n",
            solution=code_snippet,
            hints=[f"Look at the {pattern_name} pattern.", "Check the codebase for examples."],
        )
        self.add_exercise(exercise)
        return exercise

    def list_exercises(
        self,
        skill: str | None = None,
        difficulty: int | None = None,
    ) -> list[Exercise]:
        result = list(self._exercises.values())
        if skill:
            result = [e for e in result if e.skill == skill]
        if difficulty is not None:
            result = [e for e in result if e.difficulty == difficulty]
        return sorted(result, key=lambda e: (e.difficulty, e.title))

    def get_exercise(self, exercise_id: str) -> Exercise | None:
        return self._exercises.get(exercise_id)

    def submit(self, exercise_id: str, code: str) -> Submission:
        exercise = self._exercises.get(exercise_id)
        if exercise is None:
            return Submission(
                exercise_id=exercise_id,
                code=code,
                timestamp=time.time(),
                passed=False,
                score=0.0,
                feedback="Exercise not found.",
            )
        passed, score, feedback = self._grader(code, exercise.solution)
        sub = Submission(
            exercise_id=exercise_id,
            code=code,
            timestamp=time.time(),
            passed=passed,
            score=score,
            feedback=feedback,
        )
        self._submissions.append(sub)
        return sub

    @property
    def submissions(self) -> list[Submission]:
        return list(self._submissions)

    def stats(self) -> dict[str, Any]:
        total = len(self._submissions)
        passed = sum(1 for s in self._submissions if s.passed)
        return {
            "total_submissions": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total else 0.0,
            "exercises_available": len(self._exercises),
        }

    def format_summary(self) -> str:
        s = self.stats()
        return (
            f"Exercises: {s['exercises_available']}, "
            f"Submissions: {s['total_submissions']}, "
            f"Passed: {s['passed']}, "
            f"Rate: {s['pass_rate']:.0%}"
        )
