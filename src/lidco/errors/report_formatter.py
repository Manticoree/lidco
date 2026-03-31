"""Q152: Format comprehensive error reports."""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Optional

from lidco.errors.categorizer import ErrorCategorizer
from lidco.errors.friendly_messages import FriendlyMessages
from lidco.errors.solution_suggester import SolutionSuggester


@dataclass
class ErrorReport:
    error_type: str
    message: str
    category: Optional[str]
    friendly_message: Optional[str]
    suggestions: list[str]
    traceback_summary: str
    timestamp: float
    context: dict


class ErrorReportFormatter:
    """Combine categorization, friendly messages, and solution suggestions into a single report."""

    def __init__(
        self,
        categorizer: ErrorCategorizer | None = None,
        translator: FriendlyMessages | None = None,
        suggester: SolutionSuggester | None = None,
    ) -> None:
        self._categorizer = categorizer
        self._translator = translator
        self._suggester = suggester

    # ------------------------------------------------------------------
    # Report creation
    # ------------------------------------------------------------------

    def create_report(
        self,
        error: Exception,
        context: dict | None = None,
    ) -> ErrorReport:
        """Build a full ErrorReport by running the categorize/translate/suggest pipeline."""
        ctx = dict(context) if context else {}

        # Category
        cat_name: Optional[str] = None
        if self._categorizer:
            ce = self._categorizer.categorize(error)
            if ce.category:
                cat_name = ce.category.name

        # Friendly message
        friendly: Optional[str] = None
        if self._translator:
            fe = self._translator.translate(error)
            friendly = fe.friendly

        # Suggestions
        suggestions: list[str] = []
        if self._suggester:
            sols = self._suggester.suggest(error, ctx)
            for sol in sols:
                suggestions.extend(sol.steps)

        # Traceback
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_summary = "".join(tb_lines).strip()

        return ErrorReport(
            error_type=type(error).__name__,
            message=str(error),
            category=cat_name,
            friendly_message=friendly,
            suggestions=suggestions,
            traceback_summary=tb_summary,
            timestamp=time.time(),
            context=ctx,
        )

    # ------------------------------------------------------------------
    # Formatters
    # ------------------------------------------------------------------

    def format_short(self, report: ErrorReport) -> str:
        """One-line summary."""
        cat = f" [{report.category}]" if report.category else ""
        return f"{report.error_type}{cat}: {report.message}"

    def format_detailed(self, report: ErrorReport) -> str:
        """Multi-section detailed report."""
        sections: list[str] = []
        sections.append(f"=== Error Report ===")
        sections.append(f"Type: {report.error_type}")
        sections.append(f"Message: {report.message}")
        if report.category:
            sections.append(f"Category: {report.category}")
        if report.friendly_message:
            sections.append(f"Summary: {report.friendly_message}")
        if report.suggestions:
            sections.append("Suggestions:")
            for i, s in enumerate(report.suggestions, 1):
                sections.append(f"  {i}. {s}")
        if report.traceback_summary:
            sections.append("Traceback:")
            sections.append(report.traceback_summary)
        if report.context:
            sections.append(f"Context: {json.dumps(report.context)}")
        return "\n".join(sections)

    def format_json(self, report: ErrorReport) -> str:
        """JSON representation for structured logging."""
        data = {
            "error_type": report.error_type,
            "message": report.message,
            "category": report.category,
            "friendly_message": report.friendly_message,
            "suggestions": report.suggestions,
            "traceback_summary": report.traceback_summary,
            "timestamp": report.timestamp,
            "context": report.context,
        }
        return json.dumps(data, indent=2)
