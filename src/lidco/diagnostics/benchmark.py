"""Performance benchmark — Task 849."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    ops_per_second: float


class PerfBenchmark:
    """Run micro-benchmarks on callables."""

    def __init__(self) -> None:
        self._history: list[BenchmarkResult] = []

    @property
    def history(self) -> list[BenchmarkResult]:
        """All benchmark results collected so far."""
        return list(self._history)

    def run(self, name: str, fn: Callable, iterations: int = 100) -> BenchmarkResult:
        """Benchmark *fn* over *iterations* calls."""
        times: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            times.append(time.perf_counter() - t0)

        total = sum(times)
        avg = total / iterations
        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total,
            avg_time=avg,
            min_time=min(times),
            max_time=max(times),
            ops_per_second=iterations / total if total > 0 else float("inf"),
        )
        self._history.append(result)
        return result

    def compare(
        self,
        name_a: str,
        fn_a: Callable,
        name_b: str,
        fn_b: Callable,
        iterations: int = 100,
    ) -> dict:
        """Compare two functions, return winner and speedup ratio."""
        result_a = self.run(name_a, fn_a, iterations)
        result_b = self.run(name_b, fn_b, iterations)

        if result_a.avg_time <= result_b.avg_time:
            winner = name_a
            speedup = result_b.avg_time / result_a.avg_time if result_a.avg_time > 0 else float("inf")
        else:
            winner = name_b
            speedup = result_a.avg_time / result_b.avg_time if result_b.avg_time > 0 else float("inf")

        return {
            "winner": winner,
            "speedup": round(speedup, 2),
            "a": result_a,
            "b": result_b,
        }

    def suite(
        self,
        benchmarks: dict[str, Callable],
        iterations: int = 100,
    ) -> list[BenchmarkResult]:
        """Run a suite of named benchmarks."""
        results: list[BenchmarkResult] = []
        for name, fn in benchmarks.items():
            results.append(self.run(name, fn, iterations))
        return results

    @staticmethod
    def format_result(result: BenchmarkResult) -> str:
        """Human-readable single-result string."""
        return (
            f"{result.name}: {result.iterations} iterations, "
            f"avg={result.avg_time * 1000:.3f}ms, "
            f"min={result.min_time * 1000:.3f}ms, "
            f"max={result.max_time * 1000:.3f}ms, "
            f"{result.ops_per_second:.0f} ops/s"
        )
