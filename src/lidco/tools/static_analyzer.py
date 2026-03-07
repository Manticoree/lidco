"""Static analysis tool — runs ruff and mypy on Python files."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

_CAP = 50


class StaticAnalyzerTool(BaseTool):
    """Run ruff and/or mypy static analysis on Python files."""

    @property
    def name(self) -> str:
        return "run_static_analysis"

    @property
    def description(self) -> str:
        return (
            "Run ruff and/or mypy static analysis on Python files. "
            "Returns structured issues."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="paths",
                type="array",
                description="Python files or directories to analyse. Empty = current directory.",
                required=False,
                default=[],
            ),
            ToolParameter(
                name="checks",
                type="array",
                description="Which checkers to run: 'ruff', 'mypy', or both.",
                required=False,
                default=["ruff", "mypy"],
            ),
            ToolParameter(
                name="fix",
                type="boolean",
                description="Apply ruff --fix to auto-correct fixable issues.",
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_ruff(self, paths: list[str], fix: bool) -> list[dict[str, Any]]:
        """Run ruff and return a list of issue dicts."""
        cmd = [
            "ruff",
            "check",
            "--select=E,F,W,B,C4,I",
            "--output-format=json",
        ]
        if fix:
            cmd.append("--fix")
        cmd.extend(paths)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await process.communicate()
            raw = stdout.decode("utf-8", errors="replace").strip()
        except FileNotFoundError:
            return []

        if not raw:
            return []

        try:
            objects = json.loads(raw)
        except json.JSONDecodeError:
            return []

        issues: list[dict[str, Any]] = []
        for obj in objects:
            code: str = obj.get("code", "?")
            severity = "ERROR" if code and code[0] == "E" else "WARNING"
            issues.append(
                {
                    "file": obj.get("filename", ""),
                    "line": obj.get("location", {}).get("row", 0),
                    "col": obj.get("location", {}).get("column", 0),
                    "severity": severity,
                    "rule": code,
                    "message": obj.get("message", ""),
                    "checker": "ruff",
                }
            )
        return issues

    async def _run_mypy(self, paths: list[str]) -> list[dict[str, Any]]:
        """Run mypy and return a list of issue dicts."""
        cmd = [
            "mypy",
            "--ignore-missing-imports",
            "--no-error-summary",
        ] + paths

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await process.communicate()
            raw = stdout.decode("utf-8", errors="replace")
        except FileNotFoundError:
            return []

        pattern = re.compile(
            r"^(.+?):(\d+):\s*(error|warning|note):\s*(.+?)(?:\s+\[(.+?)\])?$"
        )
        issues: list[dict[str, Any]] = []
        for line in raw.splitlines():
            m = pattern.match(line)
            if not m:
                continue
            file_, lineno, level, msg, rule = m.groups()
            issues.append(
                {
                    "file": file_,
                    "line": int(lineno),
                    "col": 0,
                    "severity": level.upper(),
                    "rule": rule if rule else "mypy",
                    "message": msg,
                    "checker": "mypy",
                }
            )
        return issues

    # ------------------------------------------------------------------
    # _run
    # ------------------------------------------------------------------

    async def _run(self, **kwargs: Any) -> ToolResult:
        paths: list[str] = list(kwargs.get("paths", []))
        if not paths:
            paths = ["."]
        checks: list[str] = list(kwargs.get("checks", ["ruff", "mypy"]))
        fix: bool = bool(kwargs.get("fix", False))

        issues: list[dict[str, Any]] = []

        if "ruff" in checks:
            issues.extend(await self._run_ruff(paths, fix))
        if "mypy" in checks:
            issues.extend(await self._run_mypy(paths))

        total_before_cap = len(issues)

        # Sort: ERROR first, then by file, then line
        issues.sort(
            key=lambda i: (
                0 if i["severity"] == "ERROR" else 1,
                i["file"],
                i["line"],
            )
        )

        capped_issues = issues[:_CAP]

        errors = sum(1 for i in capped_issues if i["severity"] == "ERROR")
        warnings = sum(1 for i in capped_issues if i["severity"] in ("WARNING", "NOTE"))
        total = len(capped_issues)

        # Build output
        lines: list[str] = [
            f"Static Analysis: {total_before_cap} issues "
            f"({sum(1 for i in issues if i['severity'] == 'ERROR')} errors, "
            f"{sum(1 for i in issues if i['severity'] != 'ERROR')} warnings)"
        ]

        error_issues = [i for i in capped_issues if i["severity"] == "ERROR"]
        warning_issues = [i for i in capped_issues if i["severity"] != "ERROR"]

        if error_issues:
            lines.append("Errors:")
            for i in error_issues:
                lines.append(f"  {i['file']}:{i['line']}: {i['rule']} {i['message']} [{i['checker']}]")

        if warning_issues:
            lines.append("Warnings:")
            for i in warning_issues:
                lines.append(f"  {i['file']}:{i['line']}: {i['rule']} {i['message']} [{i['checker']}]")

        if total_before_cap > _CAP:
            lines.append(f"(showing first {_CAP} of {total_before_cap} issues)")

        output = "\n".join(lines)

        total_errors = sum(1 for i in issues if i["severity"] == "ERROR")
        total_warnings = sum(1 for i in issues if i["severity"] != "ERROR")

        return ToolResult(
            output=output,
            success=(total_errors == 0),
            metadata={
                "total": total_before_cap,
                "errors": total_errors,
                "warnings": total_warnings,
                "issues": capped_issues,
            },
        )
