"""Suggest optimizations for Python source code."""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass


class OptimizationType(str, enum.Enum):
    """Kind of optimization."""

    CACHING = "caching"
    LAZY_LOADING = "lazy_loading"
    BATCHING = "batching"
    ALGORITHM_SWAP = "algorithm_swap"
    PARALLELIZATION = "parallelization"


@dataclass(frozen=True)
class Optimization:
    """A suggested optimization."""

    type: OptimizationType
    target: str
    description: str
    estimated_impact: str = "medium"
    code_snippet: str = ""


class OptimizationAdvisor:
    """Analyze source code and suggest performance optimizations."""

    def __init__(self) -> None:
        pass

    def analyze(self, source: str, file: str = "") -> list[Optimization]:
        """Run all suggestion passes and return combined results."""
        results: list[Optimization] = []
        results.extend(self.suggest_caching(source))
        results.extend(self.suggest_batching(source))
        return results

    def suggest_caching(self, source: str) -> list[Optimization]:
        """Detect repeated expensive calls that could be cached."""
        results: list[Optimization] = []
        lines = source.splitlines()
        call_pattern = re.compile(r"(\w+\([^)]*\))")
        seen: dict[str, int] = {}
        for line in lines:
            for m in call_pattern.finditer(line):
                call = m.group(1)
                seen[call] = seen.get(call, 0) + 1
        for call, count in seen.items():
            if count >= 3:
                results.append(
                    Optimization(
                        type=OptimizationType.CACHING,
                        target=call,
                        description=f"'{call}' called {count} times — consider caching",
                        estimated_impact="medium",
                        code_snippet=f"_cache = {call}  # reuse cached value",
                    )
                )
        return results

    def suggest_batching(self, source: str) -> list[Optimization]:
        """Detect loop-of-calls patterns that could be batched."""
        results: list[Optimization] = []
        lines = source.splitlines()
        loop_re = re.compile(r"^\s*(for |while )")
        call_re = re.compile(r"(\w+\.\w+)\(")
        for i, line in enumerate(lines):
            if not loop_re.match(line):
                continue
            indent = len(line) - len(line.lstrip())
            calls_in_loop: set[str] = set()
            for j in range(i + 1, min(i + 30, len(lines))):
                inner = lines[j]
                if inner.strip() == "":
                    continue
                inner_indent = len(inner) - len(inner.lstrip())
                if inner_indent <= indent:
                    break
                for m in call_re.finditer(inner):
                    calls_in_loop.add(m.group(1))
            io_hints = {"db.execute", "api.call", "requests.get", "requests.post",
                        "conn.send", "client.fetch", "http.get", "http.post"}
            for call in calls_in_loop:
                if call in io_hints or "send" in call or "fetch" in call:
                    results.append(
                        Optimization(
                            type=OptimizationType.BATCHING,
                            target=call,
                            description=f"'{call}' inside loop — consider batching",
                            estimated_impact="high",
                            code_snippet=f"# Batch {call} calls outside loop",
                        )
                    )
        return results

    def summary(self, optimizations: list[Optimization]) -> str:
        """Human-readable summary."""
        if not optimizations:
            return "No optimizations suggested."
        lines = [f"Optimizations: {len(optimizations)}"]
        for o in optimizations:
            lines.append(
                f"  [{o.estimated_impact}] {o.type.value}: {o.description}"
            )
        return "\n".join(lines)
