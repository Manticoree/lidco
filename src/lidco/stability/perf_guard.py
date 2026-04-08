"""
Performance Regression Guard.

Tracks test execution times, flags slow tests, detects regressions,
and suggests parallelization strategies.
"""
from __future__ import annotations

import math


class PerformanceRegressionGuard:
    """Guards against test performance regressions."""

    def __init__(self, slow_threshold: float = 5.0) -> None:
        self.slow_threshold = slow_threshold
        self._test_times: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track_times(self, test_times: dict[str, float]) -> None:
        """Record test execution times.

        Args:
            test_times: Mapping of test name -> duration in seconds.
        """
        self._test_times = dict(test_times)

    def flag_slow_tests(self) -> list[dict]:
        """Return tests exceeding the slow threshold.

        Returns:
            List of dicts with "test_name", "duration", "threshold", "over_by".
        """
        slow: list[dict] = []
        for name, duration in self._test_times.items():
            if duration > self.slow_threshold:
                slow.append(
                    {
                        "test_name": name,
                        "duration": duration,
                        "threshold": self.slow_threshold,
                        "over_by": round(duration - self.slow_threshold, 4),
                    }
                )
        # Sort by duration descending
        slow.sort(key=lambda x: x["duration"], reverse=True)
        return slow

    def detect_regressions(
        self,
        previous_times: dict[str, float],
        current_times: dict[str, float],
    ) -> list[dict]:
        """Find tests that got significantly slower (>50% increase).

        Args:
            previous_times: Mapping test_name -> previous duration.
            current_times:  Mapping test_name -> current duration.

        Returns:
            List of dicts with "test_name", "previous", "current", "increase_pct".
        """
        regressions: list[dict] = []
        for name, current in current_times.items():
            previous = previous_times.get(name)
            if previous is None or previous <= 0:
                continue
            increase_pct = ((current - previous) / previous) * 100.0
            if increase_pct > 50.0:
                regressions.append(
                    {
                        "test_name": name,
                        "previous": previous,
                        "current": current,
                        "increase_pct": round(increase_pct, 2),
                    }
                )
        regressions.sort(key=lambda x: x["increase_pct"], reverse=True)
        return regressions

    def suggest_parallelization(
        self,
        test_times: dict[str, float],
        num_workers: int = 4,
    ) -> dict:
        """Suggest how to split tests across workers.

        Uses a greedy bin-packing approach (longest processing time first)
        to approximately minimize the makespan.

        Args:
            test_times: Mapping of test name -> duration.
            num_workers: Number of parallel workers.

        Returns:
            Dict with:
              "workers"        — list of lists (each inner list is test names for one worker),
              "estimated_time" — estimated wall-clock time (max worker load),
              "speedup"        — sequential_time / estimated_time.
        """
        if not test_times:
            return {
                "workers": [[] for _ in range(num_workers)],
                "estimated_time": 0.0,
                "speedup": 1.0,
            }

        # Sort tests longest-first
        sorted_tests = sorted(test_times.items(), key=lambda x: x[1], reverse=True)

        workers: list[list[str]] = [[] for _ in range(num_workers)]
        worker_loads: list[float] = [0.0] * num_workers

        for test_name, duration in sorted_tests:
            # Assign to the least-loaded worker
            min_idx = worker_loads.index(min(worker_loads))
            workers[min_idx].append(test_name)
            worker_loads[min_idx] += duration

        sequential_time = sum(test_times.values())
        estimated_time = max(worker_loads) if worker_loads else 0.0
        speedup = sequential_time / estimated_time if estimated_time > 0 else 1.0

        return {
            "workers": workers,
            "estimated_time": round(estimated_time, 4),
            "speedup": round(speedup, 4),
        }
