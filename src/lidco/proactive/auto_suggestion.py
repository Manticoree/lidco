"""Auto-suggestion pipeline combining SuggestionEngine + SmellDetector — Q126."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.proactive.suggestion_engine import Suggestion, SuggestionEngine
from lidco.proactive.smell_detector import Smell, SmellDetector


@dataclass
class AutoSuggestionResult:
    suggestions: list[Suggestion] = field(default_factory=list)
    smells: list[Smell] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.suggestions) + len(self.smells)


class AutoSuggestion:
    """Unified pipeline for suggestions and smell detection."""

    def __init__(
        self,
        engine: SuggestionEngine = None,
        detector: SmellDetector = None,
    ) -> None:
        self._engine = engine or SuggestionEngine.with_defaults()
        self._detector = detector or SmellDetector()

    def run(self, code: str, filename: str = "") -> AutoSuggestionResult:
        suggestions = self._engine.analyze(code, filename)
        smells = self._detector.detect(code, filename)
        return AutoSuggestionResult(suggestions=suggestions, smells=smells)

    def run_on_files(self, files: dict[str, str]) -> dict[str, AutoSuggestionResult]:
        results: dict[str, AutoSuggestionResult] = {}
        for fname, code in files.items():
            suggestions = self._engine.analyze(code, fname)
            smells = self._detector.detect(code, fname)
            results[fname] = AutoSuggestionResult(suggestions=suggestions, smells=smells)
        # Also detect duplicates across files
        dup_smells = self._detector.detect_duplicates(files)
        if dup_smells:
            sentinel = "__duplicates__"
            if sentinel in results:
                results[sentinel].smells.extend(dup_smells)
            else:
                results[sentinel] = AutoSuggestionResult(smells=dup_smells)
        return results

    def summary(self, results: dict[str, AutoSuggestionResult]) -> str:
        total_s = sum(r.total for r in results.values())
        total_sugg = sum(len(r.suggestions) for r in results.values())
        total_smell = sum(len(r.smells) for r in results.values())
        lines = [
            f"AutoSuggestion summary: {len(results)} file(s), {total_s} total findings",
            f"  Suggestions: {total_sugg}",
            f"  Smells:      {total_smell}",
        ]
        return "\n".join(lines)
