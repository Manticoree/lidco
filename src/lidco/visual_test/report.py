"""Visual Test Report — HTML report with side-by-side, overlay mode,
filter by status, export, and CI integration."""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---- Data classes --------------------------------------------------------


@dataclass(frozen=True)
class ReportEntry:
    """A single test comparison entry for the report."""

    name: str
    status: str  # "pass", "fail", "new", "error"
    diff_percentage: float = 0.0
    baseline_sha: str = ""
    current_sha: str = ""
    diff_pixels: int = 0
    total_pixels: int = 0
    error: str = ""
    url: str = ""
    device: str = ""


@dataclass(frozen=True)
class ReportSummary:
    """Aggregate summary across all entries."""

    total: int
    passed: int
    failed: int
    new_baselines: int
    errors: int


@dataclass(frozen=True)
class ReportConfig:
    """Configuration for report generation."""

    title: str = "Visual Regression Report"
    output_dir: str = ".lidco/reports"
    include_images: bool = True
    overlay_opacity: float = 0.5
    ci_mode: bool = False


# ---- VisualTestReport ----------------------------------------------------


class VisualTestReport:
    """Generate HTML visual regression reports."""

    def __init__(self, config: ReportConfig | None = None) -> None:
        self._config = config or ReportConfig()
        self._entries: list[ReportEntry] = []

    # -- properties --------------------------------------------------------

    @property
    def config(self) -> ReportConfig:
        return self._config

    @property
    def entries(self) -> list[ReportEntry]:
        return list(self._entries)

    # -- public API --------------------------------------------------------

    def add_entry(self, entry: ReportEntry) -> None:
        """Add a test result entry to the report."""
        self._entries = [*self._entries, entry]

    def summary(self) -> ReportSummary:
        """Compute aggregate summary."""
        total = len(self._entries)
        passed = sum(1 for e in self._entries if e.status == "pass")
        failed = sum(1 for e in self._entries if e.status == "fail")
        new_bl = sum(1 for e in self._entries if e.status == "new")
        errors = sum(1 for e in self._entries if e.status == "error")
        return ReportSummary(total=total, passed=passed, failed=failed,
                             new_baselines=new_bl, errors=errors)

    def filter_entries(self, status: str | None = None) -> list[ReportEntry]:
        """Return entries filtered by status."""
        if status is None:
            return list(self._entries)
        return [e for e in self._entries if e.status == status]

    def generate_html(self) -> str:
        """Generate a complete HTML report string."""
        s = self.summary()
        rows = self._build_rows()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        return _HTML_TEMPLATE.format(
            title=html.escape(self._config.title),
            timestamp=timestamp,
            total=s.total,
            passed=s.passed,
            failed=s.failed,
            new_baselines=s.new_baselines,
            errors=s.errors,
            rows=rows,
            overlay_opacity=self._config.overlay_opacity,
        )

    def save_html(self, filename: str = "report.html") -> Path:
        """Write the HTML report to disk. Returns the file path."""
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_text(self.generate_html())
        return path

    def export_json(self) -> str:
        """Export report data as JSON string."""
        s = self.summary()
        data: dict[str, Any] = {
            "title": self._config.title,
            "summary": {
                "total": s.total, "passed": s.passed,
                "failed": s.failed, "new_baselines": s.new_baselines,
                "errors": s.errors,
            },
            "entries": [
                {
                    "name": e.name, "status": e.status,
                    "diff_percentage": e.diff_percentage,
                    "diff_pixels": e.diff_pixels,
                    "total_pixels": e.total_pixels,
                    "error": e.error, "url": e.url, "device": e.device,
                }
                for e in self._entries
            ],
        }
        return json.dumps(data, indent=2)

    def save_json(self, filename: str = "report.json") -> Path:
        """Write JSON report to disk. Returns the file path."""
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        path.write_text(self.export_json())
        return path

    def ci_exit_code(self) -> int:
        """Return 0 if all pass/new, 1 if any fail/error."""
        s = self.summary()
        if s.failed > 0 or s.errors > 0:
            return 1
        return 0

    # -- private -----------------------------------------------------------

    def _build_rows(self) -> str:
        parts: list[str] = []
        for e in self._entries:
            status_class = {
                "pass": "pass", "fail": "fail",
                "new": "new", "error": "error",
            }.get(e.status, "")
            parts.append(
                f'<tr class="{status_class}">'
                f"<td>{html.escape(e.name)}</td>"
                f"<td>{html.escape(e.status)}</td>"
                f"<td>{e.diff_percentage:.2f}%</td>"
                f"<td>{e.diff_pixels}/{e.total_pixels}</td>"
                f"<td>{html.escape(e.device)}</td>"
                f"<td>{html.escape(e.error)}</td>"
                f"</tr>"
            )
        return "\n".join(parts)


# ---- HTML template -------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
.summary {{ display: flex; gap: 1rem; margin-bottom: 1rem; }}
.summary span {{ padding: 0.5rem 1rem; border-radius: 4px; }}
.pass {{ background: #d4edda; }}
.fail {{ background: #f8d7da; }}
.new {{ background: #cce5ff; }}
.error {{ background: #fff3cd; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
th {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>Generated: {timestamp}</p>
<div class="summary">
<span>Total: {total}</span>
<span class="pass">Passed: {passed}</span>
<span class="fail">Failed: {failed}</span>
<span class="new">New: {new_baselines}</span>
<span class="error">Errors: {errors}</span>
</div>
<table>
<thead><tr><th>Name</th><th>Status</th><th>Diff %</th><th>Pixels</th><th>Device</th><th>Error</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>"""
