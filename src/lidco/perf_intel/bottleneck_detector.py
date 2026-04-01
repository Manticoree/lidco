"""Static analysis for performance anti-patterns."""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass


class BottleneckType(str, enum.Enum):
    """Classification of performance bottlenecks."""

    QUADRATIC_LOOP = "quadratic_loop"
    REPEATED_CALL = "repeated_call"
    UNNECESSARY_COPY = "unnecessary_copy"
    BLOCKING_IO = "blocking_io"
    LARGE_ALLOCATION = "large_allocation"


@dataclass(frozen=True)
class Bottleneck:
    """A detected performance bottleneck."""

    type: BottleneckType
    file: str
    line: int = 0
    description: str = ""
    severity: str = "medium"
    suggestion: str = ""


class BottleneckDetector:
    """Detect performance anti-patterns in Python source code."""

    def __init__(self) -> None:
        pass

    def detect(self, source: str, file: str = "") -> list[Bottleneck]:
        """Run all detection passes on *source*."""
        results: list[Bottleneck] = []
        results.extend(self._detect_nested_loops(source, file))
        results.extend(self._detect_repeated_calls(source, file))
        results.extend(self._detect_large_allocations(source, file))
        return results

    def _detect_nested_loops(self, source: str, file: str) -> list[Bottleneck]:
        """Detect nested for-loops (potential O(n^2))."""
        results: list[Bottleneck] = []
        lines = source.splitlines()
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped.startswith("for "):
                continue
            indent = len(line) - len(stripped)
            # Look for a deeper for-loop in the next lines
            for j in range(i + 1, min(i + 50, len(lines))):
                inner = lines[j]
                inner_stripped = inner.lstrip()
                inner_indent = len(inner) - len(inner_stripped)
                if inner_stripped == "":
                    continue
                if inner_indent <= indent:
                    break
                if inner_stripped.startswith("for "):
                    results.append(
                        Bottleneck(
                            type=BottleneckType.QUADRATIC_LOOP,
                            file=file,
                            line=j + 1,
                            description="Nested for-loop detected — potential O(n^2)",
                            severity="high",
                            suggestion="Consider using a set/dict lookup or itertools.",
                        )
                    )
                    break
        return results

    def _detect_repeated_calls(self, source: str, file: str) -> list[Bottleneck]:
        """Detect the same function call appearing in a loop body."""
        results: list[Bottleneck] = []
        lines = source.splitlines()
        loop_pattern = re.compile(r"^\s*(for |while )")
        call_pattern = re.compile(r"(\w+\.\w+\([^)]*\))")
        for i, line in enumerate(lines):
            if not loop_pattern.match(line):
                continue
            indent = len(line) - len(line.lstrip())
            calls_seen: dict[str, int] = {}
            for j in range(i + 1, min(i + 30, len(lines))):
                inner = lines[j]
                inner_indent = len(inner) - len(inner.lstrip())
                if inner.strip() == "":
                    continue
                if inner_indent <= indent:
                    break
                for m in call_pattern.finditer(inner):
                    call = m.group(1)
                    calls_seen[call] = calls_seen.get(call, 0) + 1
            for call, count in calls_seen.items():
                if count >= 2:
                    results.append(
                        Bottleneck(
                            type=BottleneckType.REPEATED_CALL,
                            file=file,
                            line=i + 1,
                            description=f"Repeated call '{call}' in loop body",
                            severity="medium",
                            suggestion="Hoist the call above the loop or cache the result.",
                        )
                    )
        return results

    def _detect_large_allocations(
        self, source: str, file: str
    ) -> list[Bottleneck]:
        """Detect patterns that allocate large data structures."""
        results: list[Bottleneck] = []
        lines = source.splitlines()
        pattern = re.compile(r"\[.{0,5}\]\s*\*\s*(\d+)")
        for i, line in enumerate(lines):
            m = pattern.search(line)
            if m:
                size = int(m.group(1))
                if size >= 10_000:
                    results.append(
                        Bottleneck(
                            type=BottleneckType.LARGE_ALLOCATION,
                            file=file,
                            line=i + 1,
                            description=f"Large allocation of {size} elements",
                            severity="medium",
                            suggestion="Consider using a generator or numpy array.",
                        )
                    )
        return results

    def summary(self, bottlenecks: list[Bottleneck]) -> str:
        """Human-readable summary of bottlenecks."""
        if not bottlenecks:
            return "No bottlenecks detected."
        lines = [f"Bottlenecks: {len(bottlenecks)}"]
        for b in bottlenecks:
            lines.append(
                f"  [{b.severity}] {b.type.value} at {b.file}:{b.line} — {b.description}"
            )
        return "\n".join(lines)
