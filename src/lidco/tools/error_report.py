"""ErrorReportTool — structured error report for agents."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

if TYPE_CHECKING:
    from lidco.core.errors import ErrorHistory


class ErrorReportTool(BaseTool):
    """Generate a structured Markdown report of recent tool errors.

    Agents — especially the debugger — can call this at the start of a
    debugging session to get an immediate overview of what failed, grouped
    by file, error type, agent, or in flat chronological order.
    """

    def __init__(self, error_history: ErrorHistory) -> None:
        self._error_history = error_history

    @property
    def name(self) -> str:
        return "error_report"

    @property
    def description(self) -> str:
        return (
            "Show a structured report of recent tool errors, "
            "grouped by file, type, agent, or ungrouped. "
            "Call this at the start of a debugging session to get an "
            "overview of what failed before diving into individual files."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="n",
                type="integer",
                description="Number of recent errors to include (default 20).",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="group_by",
                type="string",
                description=(
                    "Grouping key: 'file' (by failing file), 'type' (by error class), "
                    "'agent' (by agent name), or 'none' (flat chronological list)."
                ),
                required=False,
                default="file",
                enum=["file", "type", "agent", "none"],
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, *, n: int = 20, group_by: str = "file") -> ToolResult:
        records = self._error_history.get_recent(n)
        if not records:
            return ToolResult(output="No errors recorded in this session.", success=True)

        if group_by == "none":
            return ToolResult(output=self._render_flat(records), success=True)

        key_fns: dict[str, Any] = {
            "file": lambda r: r.file_hint or "(no file)",
            "type": lambda r: r.error_type,
            "agent": lambda r: r.agent_name,
        }
        key_fn = key_fns.get(group_by, key_fns["file"])

        groups: dict[str, list[Any]] = defaultdict(list)
        for rec in records:
            groups[key_fn(rec)].append(rec)

        total = sum(r.occurrence_count for r in records)
        lines: list[str] = [
            f"# Error Report ({total} occurrence{'s' if total != 1 else ''}, "
            f"grouped by {group_by})\n"
        ]
        for key in sorted(groups, key=lambda k: -sum(r.occurrence_count for r in groups[k])):
            group = groups[key]
            group_total = sum(r.occurrence_count for r in group)
            lines.append(
                f"## {key} "
                f"({group_total} occurrence{'s' if group_total != 1 else ''})\n"
            )
            for rec in group:
                ts = rec.timestamp.strftime("%H:%M:%S")
                repeat = f" ×{rec.occurrence_count}" if rec.occurrence_count > 1 else ""
                args_hint = ""
                if rec.tool_args:
                    compact = ", ".join(
                        f"{k}={v!r}" for k, v in list(rec.tool_args.items())[:3]
                    )
                    args_hint = f" ({compact})"
                    if len(args_hint) > 80:
                        args_hint = args_hint[:80] + "...)"
                lines.append(
                    f"- [{ts}] `{rec.tool_name}`{args_hint}{repeat}: {rec.message[:100]}"
                )
            lines.append("")

        return ToolResult(
            output="\n".join(lines),
            success=True,
            metadata={"total_errors": total, "unique_records": len(records)},
        )

    @staticmethod
    def _render_flat(records: list[Any]) -> str:
        total = sum(r.occurrence_count for r in records)
        lines: list[str] = [f"# Error Report ({total} error occurrence{'s' if total != 1 else ''})\n"]
        for rec in records:
            ts = rec.timestamp.strftime("%H:%M:%S")
            repeat = f" ×{rec.occurrence_count}" if rec.occurrence_count > 1 else ""
            hint = f" [{rec.file_hint}]" if rec.file_hint else ""
            lines.append(
                f"- [{ts}] `{rec.tool_name}` ({rec.agent_name}){repeat}{hint}: "
                f"{rec.message[:100]}"
            )
        return "\n".join(lines)
