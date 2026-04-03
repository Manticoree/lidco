"""Real-time stream statistics and anomaly detection."""
from __future__ import annotations

import time


class StreamMonitor:
    """Track token throughput, latency percentiles, and stall detection.

    Designed for lightweight, always-on monitoring of streaming sessions.
    """

    def __init__(self) -> None:
        self._timestamps: list[float] = []
        self._intervals: list[float] = []
        self._total_tokens = 0
        self._start_time: float | None = None
        self._last_token_time: float | None = None

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, token: str) -> None:  # noqa: ARG002
        """Record a token arrival event.

        Parameters
        ----------
        token:
            The token string (used for counting; content is not stored).
        """
        now = time.monotonic()

        if self._start_time is None:
            self._start_time = now

        if self._last_token_time is not None:
            self._intervals.append(now - self._last_token_time)

        self._last_token_time = now
        self._timestamps.append(now)
        self._total_tokens += 1

    # ------------------------------------------------------------------
    # Throughput
    # ------------------------------------------------------------------

    def tokens_per_second(self) -> float:
        """Return the overall tokens-per-second rate since monitoring began."""
        if self._start_time is None or self._total_tokens == 0:
            return 0.0
        elapsed = time.monotonic() - self._start_time
        if elapsed <= 0:
            return 0.0
        return self._total_tokens / elapsed

    # ------------------------------------------------------------------
    # Latency percentiles
    # ------------------------------------------------------------------

    def latency_percentiles(self) -> dict:
        """Return p50, p90 and p99 inter-token latencies in seconds."""
        if not self._intervals:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0}

        sorted_intervals = sorted(self._intervals)
        n = len(sorted_intervals)

        def _percentile(p: float) -> float:
            idx = int(p / 100.0 * (n - 1))
            idx = max(0, min(idx, n - 1))
            return sorted_intervals[idx]

        return {
            "p50": round(_percentile(50), 6),
            "p90": round(_percentile(90), 6),
            "p99": round(_percentile(99), 6),
        }

    # ------------------------------------------------------------------
    # Stall detection
    # ------------------------------------------------------------------

    def detect_stall(self, threshold_seconds: float = 5.0) -> bool:
        """Return ``True`` if no token has arrived for *threshold_seconds*."""
        if self._last_token_time is None:
            return False
        return (time.monotonic() - self._last_token_time) >= threshold_seconds

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def alert_anomalies(self, baseline_tps: float | None = None) -> list[str]:
        """Return a list of anomaly alert strings.

        Parameters
        ----------
        baseline_tps:
            Expected tokens-per-second.  If ``None``, uses the measured
            average as the baseline and only reports stalls.
        """
        alerts: list[str] = []

        if self.detect_stall():
            gap = 0.0
            if self._last_token_time is not None:
                gap = time.monotonic() - self._last_token_time
            alerts.append(f"Stall detected: no tokens for {gap:.1f}s")

        current_tps = self.tokens_per_second()

        if baseline_tps is not None and baseline_tps > 0:
            ratio = current_tps / baseline_tps
            if ratio < 0.5:
                alerts.append(
                    f"Throughput drop: {current_tps:.1f} tps vs baseline {baseline_tps:.1f} tps"
                )
            elif ratio > 2.0:
                alerts.append(
                    f"Throughput spike: {current_tps:.1f} tps vs baseline {baseline_tps:.1f} tps"
                )

        percentiles = self.latency_percentiles()
        if percentiles["p99"] > 0 and percentiles["p50"] > 0:
            if percentiles["p99"] > percentiles["p50"] * 10:
                alerts.append(
                    f"Latency outliers: p99={percentiles['p99']:.4f}s "
                    f"is >10x p50={percentiles['p50']:.4f}s"
                )

        return alerts

    # ------------------------------------------------------------------
    # Reset / Stats
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all recorded data."""
        self._timestamps.clear()
        self._intervals.clear()
        self._total_tokens = 0
        self._start_time = None
        self._last_token_time = None

    def stats(self) -> dict:
        """Return summary statistics."""
        elapsed = 0.0
        if self._start_time is not None:
            elapsed = time.monotonic() - self._start_time

        return {
            "tps": round(self.tokens_per_second(), 2),
            "total_tokens": self._total_tokens,
            "duration": round(elapsed, 3),
            "stall_detected": self.detect_stall(),
        }
