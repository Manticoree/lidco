"""Prioritize test execution based on code changes."""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class TestPriority:
    test_path: str
    test_name: str
    priority_score: float  # 0.0-1.0, higher = run first
    reasons: list[str]


@dataclass
class ChangedFile:
    file_path: str
    added_lines: list[int] = field(default_factory=list)
    removed_lines: list[int] = field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False


class TestPrioritizer:
    def __init__(self) -> None:
        self._test_file_map: dict[str, list[str]] = {}  # source file -> [test files]
        self._failure_history: dict[str, int] = {}  # test_name -> failure count

    def register_mapping(self, source_file: str, test_files: list[str]) -> None:
        """Register which test files cover which source files."""
        self._test_file_map = {
            **self._test_file_map,
            source_file: list(test_files),
        }

    def register_failure(self, test_name: str, count: int = 1) -> None:
        """Record historical test failures."""
        self._failure_history = {
            **self._failure_history,
            test_name: self._failure_history.get(test_name, 0) + count,
        }

    @property
    def test_file_map(self) -> dict[str, list[str]]:
        return dict(self._test_file_map)

    @property
    def failure_history(self) -> dict[str, int]:
        return dict(self._failure_history)

    def prioritize(
        self, changed_files: list[ChangedFile], all_tests: list[str]
    ) -> list[TestPriority]:
        """Rank tests by priority based on changes."""
        scores: dict[str, tuple[float, list[str]]] = {}

        for test in all_tests:
            score = 0.0
            reasons: list[str] = []

            # Direct mapping: test covers a changed file
            for cf in changed_files:
                mapped_tests = self._test_file_map.get(cf.file_path, [])
                if test in mapped_tests:
                    change_size = len(cf.added_lines) + len(cf.removed_lines)
                    mapping_score = min(0.5 + change_size * 0.01, 0.8)
                    if mapping_score > score:
                        score = mapping_score
                    reasons.append(f"covers changed file {cf.file_path}")

            # Name-based heuristic: test file name matches source file
            test_basename = test.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            for cf in changed_files:
                src_basename = (
                    cf.file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                )
                src_name = src_basename.replace(".py", "")
                if src_name in test_basename:
                    heuristic_score = 0.4
                    if heuristic_score > score:
                        score = heuristic_score
                    reasons.append(f"name matches {src_basename}")

            # Failure history boost
            fail_count = self._failure_history.get(test, 0)
            if fail_count > 0:
                fail_boost = min(fail_count * 0.05, 0.2)
                score += fail_boost
                reasons.append(f"failed {fail_count} times before")

            score = min(score, 1.0)
            if reasons:
                scores[test] = (score, reasons)
            else:
                scores[test] = (0.1, ["no direct connection to changes"])

        result = [
            TestPriority(
                test_path=t,
                test_name=t.rsplit("/", 1)[-1],
                priority_score=s,
                reasons=r,
            )
            for t, (s, r) in scores.items()
        ]
        result.sort(key=lambda tp: tp.priority_score, reverse=True)
        return result

    def get_ordered_tests(
        self, changed_files: list[ChangedFile], all_tests: list[str]
    ) -> list[str]:
        """Return test paths ordered by priority."""
        priorities = self.prioritize(changed_files, all_tests)
        return [p.test_path for p in priorities]

    def infer_test_mapping(
        self, source_files: list[str], test_files: list[str]
    ) -> dict[str, list[str]]:
        """Heuristically infer source->test mapping from file names."""
        mapping: dict[str, list[str]] = {}
        for src in source_files:
            src_name = (
                src.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].replace(".py", "")
            )
            matches = [t for t in test_files if src_name in t]
            if matches:
                mapping[src] = matches
        return mapping
