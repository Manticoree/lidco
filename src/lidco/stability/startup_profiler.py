"""
Startup Profiler.

Measures import costs, identifies lazy-load opportunities, and analyses
cold-start breakdowns to help reduce application startup latency.
"""
from __future__ import annotations

import importlib
import re
import time


class StartupProfiler:
    """Profile and analyse application startup costs."""

    def __init__(self) -> None:
        self._timings: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def profile_imports(self, module_names: list[str]) -> list[dict]:
        """Measure the import cost of each module.

        Args:
            module_names: List of dotted module names to import and time.

        Returns:
            List of dicts with keys:
                "module" (str): module name
                "time_ms" (float): import time in milliseconds
                "success" (bool): True if import succeeded
                "error" (str | None): error message if import failed
        """
        results: list[dict] = []
        for name in module_names:
            start = time.perf_counter()
            error: str | None = None
            success = True
            try:
                importlib.import_module(name)
            except Exception as exc:
                success = False
                error = str(exc)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._timings[name] = elapsed_ms
            results.append(
                {
                    "module": name,
                    "time_ms": elapsed_ms,
                    "success": success,
                    "error": error,
                }
            )
        return results

    def find_lazy_opportunities(self, source_code: str) -> list[dict]:
        """Find top-level imports that could be deferred to call-site.

        Scans *source_code* for ``import`` / ``from … import`` statements at
        the module level and flags known heavy modules.

        Args:
            source_code: Python source text to analyse.

        Returns:
            List of dicts with keys:
                "line" (int): 1-based line number
                "module" (str): imported module name
                "suggestion" (str): human-readable suggestion
                "estimated_savings_ms" (float): rough savings estimate in ms
        """
        _HEAVY_MODULES: dict[str, float] = {
            "numpy": 120.0,
            "pandas": 200.0,
            "scipy": 150.0,
            "matplotlib": 180.0,
            "sklearn": 300.0,
            "tensorflow": 1500.0,
            "torch": 1200.0,
            "keras": 900.0,
            "PIL": 80.0,
            "cv2": 100.0,
            "sqlalchemy": 90.0,
            "django": 250.0,
            "flask": 60.0,
            "fastapi": 70.0,
            "boto3": 150.0,
            "requests": 40.0,
            "aiohttp": 50.0,
            "lxml": 60.0,
            "bs4": 30.0,
            "cryptography": 60.0,
        }

        opportunities: list[dict] = []
        import_re = re.compile(
            r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import\s+\w+)", re.MULTILINE
        )

        for i, line in enumerate(source_code.splitlines(), start=1):
            stripped = line.strip()
            m = import_re.match(stripped)
            if not m:
                continue
            module_name = m.group(1) or m.group(2)
            if not module_name:
                continue
            root = module_name.split(".")[0]
            if root in _HEAVY_MODULES:
                savings = _HEAVY_MODULES[root]
                opportunities.append(
                    {
                        "line": i,
                        "module": module_name,
                        "suggestion": (
                            f"Move 'import {module_name}' inside the function(s) "
                            f"that use it to defer loading"
                        ),
                        "estimated_savings_ms": savings,
                    }
                )
        return opportunities

    def analyze_cold_start(self, timings: dict[str, float]) -> dict:
        """Analyse cold-start timing breakdown.

        Args:
            timings: Mapping of module name → time in milliseconds.

        Returns:
            dict with keys:
                "total_ms" (float): sum of all timings
                "top_5" (list[tuple[str, float]]): five slowest modules
                "suggestions" (list[str]): actionable improvement suggestions
        """
        total_ms = sum(timings.values())
        sorted_items = sorted(timings.items(), key=lambda kv: kv[1], reverse=True)
        top_5 = [(name, ms) for name, ms in sorted_items[:5]]

        suggestions: list[str] = []
        for name, ms in top_5:
            if ms > 500:
                suggestions.append(
                    f"'{name}' takes {ms:.1f} ms — consider lazy import or "
                    f"splitting into a background worker"
                )
            elif ms > 100:
                suggestions.append(
                    f"'{name}' takes {ms:.1f} ms — consider lazy import"
                )

        if total_ms > 2000:
            suggestions.append(
                f"Total cold-start time {total_ms:.1f} ms exceeds 2 s — "
                f"review all heavy imports"
            )

        return {
            "total_ms": total_ms,
            "top_5": top_5,
            "suggestions": suggestions,
        }

    def generate_report(self) -> str:
        """Generate a human-readable text report from collected timings.

        Returns:
            Multi-line string report.
        """
        if not self._timings:
            return "No startup timings recorded yet."

        lines: list[str] = ["=== Startup Profiler Report ===", ""]
        analysis = self.analyze_cold_start(self._timings)
        lines.append(f"Total startup time: {analysis['total_ms']:.2f} ms")
        lines.append(f"Modules profiled  : {len(self._timings)}")
        lines.append("")
        lines.append("Top 5 slowest imports:")
        for rank, (name, ms) in enumerate(analysis["top_5"], start=1):
            lines.append(f"  {rank}. {name:40s} {ms:8.2f} ms")
        if analysis["suggestions"]:
            lines.append("")
            lines.append("Suggestions:")
            for s in analysis["suggestions"]:
                lines.append(f"  - {s}")
        return "\n".join(lines)
