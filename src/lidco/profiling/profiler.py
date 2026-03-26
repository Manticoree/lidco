"""
Code Profiler — profile Python code using cProfile and pstats.

Provides:
- Profile a callable directly
- Profile a Python file by running it
- Profile a code string snippet
- Return structured ProfileReport with hotspots, call counts, timing

Uses only stdlib: cProfile, pstats, io, time.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FunctionStat:
    """Statistics for a single profiled function."""
    module: str            # file/module name
    function: str          # function name
    line: int              # line number
    ncalls: int            # number of calls (incl. recursive)
    tottime: float         # time in function (excl. callees) seconds
    cumtime: float         # time in function (incl. callees) seconds
    percall_tot: float     # tottime / ncalls
    percall_cum: float     # cumtime / ncalls

    @property
    def qualified_name(self) -> str:
        return f"{self.module}:{self.line}({self.function})"


@dataclass
class ProfileReport:
    """Result of a profiling run."""
    label: str
    total_calls: int
    primitive_calls: int
    elapsed_ms: float
    stats: list[FunctionStat]   # sorted by cumtime desc
    raw_text: str               # full pstats output
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def top_hotspots(self, n: int = 10) -> list[FunctionStat]:
        """Return top N functions by cumulative time."""
        return self.stats[:n]

    def format_table(self, n: int = 20) -> str:
        """Format hotspots as an ASCII table."""
        if self.error:
            return f"Profile error: {self.error}"
        lines = [
            f"Profile: {self.label}",
            f"Total calls: {self.total_calls}  Primitive: {self.primitive_calls}  "
            f"Elapsed: {self.elapsed_ms:.0f}ms",
            "",
            f"{'ncalls':>8}  {'tottime':>9}  {'cumtime':>9}  {'percall':>9}  function",
            "-" * 70,
        ]
        for s in self.stats[:n]:
            lines.append(
                f"{s.ncalls:>8}  {s.tottime:>9.4f}  {s.cumtime:>9.4f}  "
                f"{s.percall_cum:>9.4f}  {s.qualified_name}"
            )
        return "\n".join(lines)

    def summary(self) -> str:
        top = self.stats[0] if self.stats else None
        if top:
            return (
                f"{self.total_calls} calls in {self.elapsed_ms:.0f}ms; "
                f"hottest: {top.function} ({top.cumtime:.4f}s)"
            )
        return f"{self.total_calls} calls in {self.elapsed_ms:.0f}ms"


# ---------------------------------------------------------------------------
# CodeProfiler
# ---------------------------------------------------------------------------

class CodeProfiler:
    """
    Profile Python code using cProfile.

    Parameters
    ----------
    sort_by : str
        Primary sort key for stats. Options: 'cumulative', 'tottime',
        'calls', 'pcalls', 'name', 'filename', 'lineno'.
    strip_dirs : bool
        Strip leading path components from file names in output.
    """

    def __init__(
        self,
        sort_by: str = "cumulative",
        strip_dirs: bool = True,
    ) -> None:
        self._sort_by = sort_by
        self._strip_dirs = strip_dirs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def profile_callable(
        self,
        func: Callable[..., Any],
        *args: Any,
        label: str | None = None,
        **kwargs: Any,
    ) -> ProfileReport:
        """
        Profile a Python callable.

        Parameters
        ----------
        func : Callable
            The function to profile.
        *args, **kwargs
            Arguments forwarded to func.
        label : str | None
            Human-readable label for the report.
        """
        lbl = label or getattr(func, "__name__", "callable")
        pr = cProfile.Profile()
        start = time.monotonic()
        try:
            pr.enable()
            try:
                func(*args, **kwargs)
            finally:
                pr.disable()
            elapsed = (time.monotonic() - start) * 1000
            return self._build_report(pr, lbl, elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ProfileReport(
                label=lbl,
                total_calls=0,
                primitive_calls=0,
                elapsed_ms=elapsed,
                stats=[],
                raw_text="",
                error=str(exc),
            )

    def profile_code(self, code: str, label: str = "snippet") -> ProfileReport:
        """
        Profile a Python code string.

        Parameters
        ----------
        code : str
            Python source code to profile.
        label : str
            Human-readable label for the report.
        """
        pr = cProfile.Profile()
        start = time.monotonic()
        try:
            compiled = compile(code, "<profiled>", "exec")
            ns: dict[str, Any] = {}
            pr.enable()
            try:
                exec(compiled, ns)  # noqa: S102
            finally:
                pr.disable()
            elapsed = (time.monotonic() - start) * 1000
            return self._build_report(pr, label, elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ProfileReport(
                label=label,
                total_calls=0,
                primitive_calls=0,
                elapsed_ms=elapsed,
                stats=[],
                raw_text="",
                error=str(exc),
            )

    def profile_file(self, path: str | Path, label: str | None = None) -> ProfileReport:
        """
        Profile a Python script file.

        Parameters
        ----------
        path : str | Path
            Path to a .py file to execute and profile.
        label : str | None
            Human-readable label (defaults to filename).
        """
        p = Path(path)
        lbl = label or p.name
        if not p.exists():
            return ProfileReport(
                label=lbl,
                total_calls=0,
                primitive_calls=0,
                elapsed_ms=0.0,
                stats=[],
                raw_text="",
                error=f"File not found: {path}",
            )
        code = p.read_text(encoding="utf-8")
        pr = cProfile.Profile()
        start = time.monotonic()
        try:
            compiled = compile(code, str(p), "exec")
            ns: dict[str, Any] = {"__file__": str(p), "__name__": "__main__"}
            pr.enable()
            try:
                exec(compiled, ns)  # noqa: S102
            finally:
                pr.disable()
            elapsed = (time.monotonic() - start) * 1000
            return self._build_report(pr, lbl, elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return ProfileReport(
                label=lbl,
                total_calls=0,
                primitive_calls=0,
                elapsed_ms=elapsed,
                stats=[],
                raw_text="",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_report(self, pr: cProfile.Profile, label: str, elapsed_ms: float) -> ProfileReport:
        """Convert a cProfile.Profile into a ProfileReport."""
        stream = io.StringIO()
        ps = pstats.Stats(pr, stream=stream)
        if self._strip_dirs:
            ps.strip_dirs()
        ps.sort_stats(self._sort_by)
        ps.print_stats()
        raw_text = stream.getvalue()

        stats_list: list[FunctionStat] = []
        for (filename, lineno, funcname), (ncalls, primitive_calls, tottime, cumtime, _callers) in ps.stats.items():
            percall_tot = tottime / ncalls if ncalls else 0.0
            percall_cum = cumtime / ncalls if ncalls else 0.0
            stats_list.append(FunctionStat(
                module=filename,
                function=funcname,
                line=lineno,
                ncalls=ncalls,
                tottime=tottime,
                cumtime=cumtime,
                percall_tot=percall_tot,
                percall_cum=percall_cum,
            ))

        # Sort by cumtime descending
        stats_list.sort(key=lambda s: s.cumtime, reverse=True)

        total_calls = sum(s.ncalls for s in stats_list)
        primitive_total = sum(s.ncalls for s in stats_list)

        return ProfileReport(
            label=label,
            total_calls=total_calls,
            primitive_calls=primitive_total,
            elapsed_ms=elapsed_ms,
            stats=stats_list,
            raw_text=raw_text,
        )
