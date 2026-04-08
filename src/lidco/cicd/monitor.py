"""
Pipeline Monitor — track pipeline runs, detect flaky tests,
compute duration trends and success rates.

All data stored in-memory (or optionally persisted to JSON).
Pure stdlib.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineRun:
    """Record of a single pipeline execution."""

    run_id: str
    pipeline: str
    status: str  # "success", "failure", "running", "cancelled"
    started_at: float  # epoch
    finished_at: float = 0.0
    duration: float = 0.0
    stages: dict[str, str] = field(default_factory=dict)  # stage -> status
    failure_reason: str = ""
    commit_sha: str = ""

    def finish(self, status: str, failure_reason: str = "") -> PipelineRun:
        """Return a new run with finished state (immutable update)."""
        now = time.time()
        return PipelineRun(
            run_id=self.run_id,
            pipeline=self.pipeline,
            status=status,
            started_at=self.started_at,
            finished_at=now,
            duration=now - self.started_at,
            stages=dict(self.stages),
            failure_reason=failure_reason,
            commit_sha=self.commit_sha,
        )


@dataclass(frozen=True)
class DurationTrend:
    """Duration trend statistics."""

    pipeline: str
    avg_duration: float
    min_duration: float
    max_duration: float
    p50_duration: float
    p95_duration: float
    total_runs: int


@dataclass(frozen=True)
class FlakyTest:
    """A test detected as flaky."""

    name: str
    failure_count: int
    total_runs: int
    flake_rate: float  # 0.0 – 1.0


@dataclass(frozen=True)
class PipelineStats:
    """Aggregate statistics for a pipeline."""

    pipeline: str
    total_runs: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration: float
    trend: DurationTrend | None = None
    flaky_tests: list[FlakyTest] = field(default_factory=list)


class PipelineMonitor:
    """Monitor CI/CD pipeline runs and compute analytics."""

    def __init__(self, storage_path: str | None = None) -> None:
        self._storage_path = storage_path
        self._runs: list[PipelineRun] = []
        self._flaky_reports: dict[str, dict[str, int]] = {}  # test -> {"fail": n, "total": n}
        if storage_path and os.path.isfile(storage_path):
            self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_run(self, run: PipelineRun) -> None:
        """Record a pipeline run."""
        self._runs = [*self._runs, run]
        self._persist()

    def get_runs(self, pipeline: str | None = None, limit: int = 50) -> list[PipelineRun]:
        """Return recent runs, optionally filtered by *pipeline*."""
        filtered = self._runs if pipeline is None else [
            r for r in self._runs if r.pipeline == pipeline
        ]
        return filtered[-limit:]

    def get_stats(self, pipeline: str) -> PipelineStats:
        """Compute aggregate stats for *pipeline*."""
        runs = [r for r in self._runs if r.pipeline == pipeline and r.status != "running"]
        if not runs:
            return PipelineStats(
                pipeline=pipeline,
                total_runs=0,
                success_count=0,
                failure_count=0,
                success_rate=0.0,
                avg_duration=0.0,
            )

        successes = [r for r in runs if r.status == "success"]
        failures = [r for r in runs if r.status == "failure"]
        durations = [r.duration for r in runs if r.duration > 0]
        avg_dur = sum(durations) / len(durations) if durations else 0.0

        trend = self._compute_trend(pipeline, runs, durations)
        flaky = self._detect_flaky()

        return PipelineStats(
            pipeline=pipeline,
            total_runs=len(runs),
            success_count=len(successes),
            failure_count=len(failures),
            success_rate=len(successes) / len(runs) if runs else 0.0,
            avg_duration=avg_dur,
            trend=trend,
            flaky_tests=flaky,
        )

    def report_test_result(self, test_name: str, passed: bool) -> None:
        """Report a test result for flaky detection."""
        entry = self._flaky_reports.get(test_name, {"fail": 0, "total": 0})
        new_entry = {
            "fail": entry["fail"] + (0 if passed else 1),
            "total": entry["total"] + 1,
        }
        self._flaky_reports = {**self._flaky_reports, test_name: new_entry}

    # ------------------------------------------------------------------
    # Trend & flaky detection
    # ------------------------------------------------------------------

    def _compute_trend(
        self, pipeline: str, runs: list[PipelineRun], durations: list[float]
    ) -> DurationTrend | None:
        if not durations:
            return None
        sorted_d = sorted(durations)
        n = len(sorted_d)
        return DurationTrend(
            pipeline=pipeline,
            avg_duration=sum(sorted_d) / n,
            min_duration=sorted_d[0],
            max_duration=sorted_d[-1],
            p50_duration=sorted_d[n // 2],
            p95_duration=sorted_d[int(n * 0.95)] if n > 1 else sorted_d[-1],
            total_runs=n,
        )

    def _detect_flaky(self) -> list[FlakyTest]:
        flaky: list[FlakyTest] = []
        for name, info in self._flaky_reports.items():
            total = info["total"]
            fails = info["fail"]
            if total >= 3 and 0 < fails < total:
                rate = fails / total
                if rate > 0.1:
                    flaky.append(
                        FlakyTest(name=name, failure_count=fails, total_runs=total, flake_rate=rate)
                    )
        return sorted(flaky, key=lambda f: f.flake_rate, reverse=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        if not self._storage_path:
            return
        data = [
            {
                "run_id": r.run_id,
                "pipeline": r.pipeline,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "duration": r.duration,
                "stages": r.stages,
                "failure_reason": r.failure_reason,
                "commit_sha": r.commit_sha,
            }
            for r in self._runs
        ]
        with open(self._storage_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load(self) -> None:
        if not self._storage_path or not os.path.isfile(self._storage_path):
            return
        with open(self._storage_path, encoding="utf-8") as fh:
            raw = fh.read().strip()
        if not raw:
            return
        data = json.loads(raw)
        self._runs = [
            PipelineRun(
                run_id=d["run_id"],
                pipeline=d["pipeline"],
                status=d["status"],
                started_at=d["started_at"],
                finished_at=d.get("finished_at", 0.0),
                duration=d.get("duration", 0.0),
                stages=d.get("stages", {}),
                failure_reason=d.get("failure_reason", ""),
                commit_sha=d.get("commit_sha", ""),
            )
            for d in data
        ]
