"""
Queue Overflow Guard — Q343.

Monitors queue depths, detects backpressure, verifies overflow prevention
in source code, and detects consumer lag.
"""
from __future__ import annotations

import re


class QueueOverflowGuard:
    """Guard against queue overflow and consumer lag issues."""

    def __init__(self, max_depth: int = 10000) -> None:
        self.max_depth = max_depth

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def monitor_depth(self, queue_sizes: dict[str, int]) -> list[dict]:
        """Check queue depths against max_depth.

        Args:
            queue_sizes: Mapping of queue_name -> current size.

        Returns dicts with "queue_name", "current_size", "max_depth",
        "status" ("ok" / "warning" / "critical").
        """
        results: list[dict] = []
        warning_threshold = self.max_depth * 0.75
        critical_threshold = self.max_depth * 0.90

        for name, size in queue_sizes.items():
            if size >= critical_threshold:
                status = "critical"
            elif size >= warning_threshold:
                status = "warning"
            else:
                status = "ok"
            results.append(
                {
                    "queue_name": name,
                    "current_size": size,
                    "max_depth": self.max_depth,
                    "status": status,
                }
            )
        return results

    def detect_backpressure(
        self,
        producer_rate: float,
        consumer_rate: float,
    ) -> dict:
        """Detect backpressure by comparing producer and consumer rates.

        Args:
            producer_rate: Items produced per second.
            consumer_rate: Items consumed per second.

        Returns "has_backpressure" (bool), "producer_rate", "consumer_rate",
        "ratio", "suggestion".
        """
        if consumer_rate <= 0:
            ratio = float("inf")
        else:
            ratio = producer_rate / consumer_rate

        has_backpressure = ratio > 1.0

        if has_backpressure:
            if ratio == float("inf"):
                suggestion = (
                    "Consumer rate is zero — queue will fill immediately. "
                    "Start consumers before producers."
                )
            elif ratio >= 2.0:
                suggestion = (
                    f"Producer is {ratio:.1f}x faster than consumer — "
                    "add more consumers or apply producer-side rate limiting."
                )
            else:
                suggestion = (
                    f"Producer slightly faster than consumer (ratio={ratio:.2f}) — "
                    "monitor queue depth; consider adding a consumer or slowing the producer."
                )
        else:
            suggestion = (
                "No backpressure detected — consumer keeps up with producer."
            )

        return {
            "has_backpressure": has_backpressure,
            "producer_rate": producer_rate,
            "consumer_rate": consumer_rate,
            "ratio": ratio,
            "suggestion": suggestion,
        }

    def check_overflow_prevention(self, source_code: str) -> list[dict]:
        """Verify queues have maxsize set to prevent unbounded growth.

        Returns dicts with "line", "queue_type", "has_maxsize" (bool),
        "suggestion".
        """
        results: list[dict] = []
        lines = source_code.splitlines()

        queue_patterns = [
            r'queue\.Queue\s*\(',
            r'queue\.PriorityQueue\s*\(',
            r'queue\.LifoQueue\s*\(',
            r'asyncio\.Queue\s*\(',
            r'asyncio\.PriorityQueue\s*\(',
            r'asyncio\.LifoQueue\s*\(',
            r'collections\.deque\s*\(',
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            for pat in queue_patterns:
                m = re.search(pat, stripped)
                if m:
                    queue_type = re.search(r'(\w+\.\w+)\s*\(', stripped)
                    qtype = queue_type.group(1) if queue_type else "Queue"

                    # Check if maxsize / maxlen argument is present.
                    has_maxsize = bool(
                        re.search(r'maxsize\s*=\s*[1-9]\d*', stripped)
                        or re.search(r'maxlen\s*=\s*[1-9]\d*', stripped)
                        or re.search(r'Queue\s*\(\s*[1-9]\d*', stripped)
                        or re.search(r'deque\s*\(\s*\w+\s*,\s*[1-9]\d*', stripped)
                    )

                    results.append(
                        {
                            "line": lineno,
                            "queue_type": qtype,
                            "has_maxsize": has_maxsize,
                            "suggestion": (
                                "Good: queue has a bounded maxsize."
                                if has_maxsize
                                else (
                                    f"'{qtype}' created without maxsize — "
                                    "set maxsize= (or maxlen= for deque) to prevent unbounded memory growth."
                                )
                            ),
                        }
                    )
                    break  # one finding per line

        return results

    def detect_consumer_lag(
        self,
        produced: int,
        consumed: int,
        time_window: float,
    ) -> dict:
        """Detect consumer lag and estimate time to overflow.

        Args:
            produced:    Total items produced in the time window.
            consumed:    Total items consumed in the time window.
            time_window: Duration of the observation window in seconds.

        Returns "lag", "lag_rate", "time_to_overflow" (float or None),
        "alert_level".
        """
        lag = produced - consumed
        lag_rate = lag / time_window if time_window > 0 else 0.0

        if lag <= 0:
            time_to_overflow = None
            alert_level = "none"
        else:
            # Estimate how long before the queue (self.max_depth) fills.
            remaining_capacity = self.max_depth - lag
            if lag_rate > 0 and remaining_capacity > 0:
                time_to_overflow = remaining_capacity / lag_rate
            elif remaining_capacity <= 0:
                time_to_overflow = 0.0
            else:
                time_to_overflow = None  # lag but not growing

            if time_to_overflow is not None and time_to_overflow <= 60:
                alert_level = "critical"
            elif time_to_overflow is not None and time_to_overflow <= 300:
                alert_level = "warning"
            elif lag > self.max_depth * 0.5:
                alert_level = "warning"
            else:
                alert_level = "info"

        return {
            "lag": lag,
            "lag_rate": round(lag_rate, 4),
            "time_to_overflow": (
                round(time_to_overflow, 2) if time_to_overflow is not None else None
            ),
            "alert_level": alert_level,
        }
