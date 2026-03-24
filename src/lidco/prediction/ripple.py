"""RippleAnalyzer — next-edit ripple propagation after symbol changes (Copilot NES parity)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

# Regex to detect changed symbol definitions in unified diff lines
_SYMBOL_PATTERNS = [
    re.compile(r"^[+-].*\bdef\s+(\w+)\s*\("),          # Python function
    re.compile(r"^[+-].*\bfunction\s+(\w+)\s*[\({]"),   # JS/TS function
    re.compile(r"^[+-].*\bconst\s+(\w+)\s*="),          # JS const
    re.compile(r"^[+-].*\btype\s+(\w+)\s*[={]"),        # TS type
    re.compile(r"^[+-].*\bclass\s+(\w+)[\s:(]"),        # Class definition
    re.compile(r"^[+-].*\bfunc\s+(\w+)\s*\("),          # Go function
]


@dataclass
class RippleEdit:
    file: str
    line: int
    original: str
    suggested: str
    reason: str
    symbol: str


@dataclass
class RippleSuggestion:
    source_file: str
    source_change: str  # the diff line that triggered this
    edits: list[RippleEdit] = field(default_factory=list)


class RippleAnalyzer:
    """Analyze a diff and suggest downstream edits for changed symbols."""

    def __init__(
        self,
        edit_graph: object | None = None,
        llm_fn: Callable[[str, str, str, str], str] | None = None,
    ) -> None:
        self._edit_graph = edit_graph
        self._llm_fn = llm_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, diff_text: str) -> list[RippleSuggestion]:
        """Parse diff, find changed symbols, locate references, suggest edits."""
        symbols = self.extract_changed_symbols(diff_text)
        suggestions: list[RippleSuggestion] = []

        for symbol in symbols:
            refs = self.find_references(symbol)
            if not refs:
                continue

            # Find the triggering diff line
            source_change = self._find_source_line(diff_text, symbol)
            source_file = self._extract_source_file(diff_text)

            edits = []
            for ref_file, ref_line in refs:
                edit = self.suggest_edit(ref_file, ref_line, symbol, source_change)
                edits.append(edit)

            suggestions.append(RippleSuggestion(
                source_file=source_file,
                source_change=source_change,
                edits=edits,
            ))

        return suggestions

    def extract_changed_symbols(self, diff: str) -> list[str]:
        """Parse unified diff and extract names of changed definitions."""
        symbols: list[str] = []
        seen: set[str] = set()
        for line in diff.splitlines():
            if not (line.startswith("+") or line.startswith("-")):
                continue
            for pattern in _SYMBOL_PATTERNS:
                m = pattern.match(line)
                if m:
                    name = m.group(1)
                    if name not in seen:
                        seen.add(name)
                        symbols.append(name)
                    break
        return symbols

    def find_references(self, symbol: str) -> list[tuple[str, int]]:
        """Find all references to symbol via edit_graph or return []."""
        if self._edit_graph is None:
            return []
        try:
            return list(self._edit_graph.find_references(symbol))
        except Exception:
            return []

    def suggest_edit(
        self, file: str, line: int, symbol: str, context: str
    ) -> RippleEdit:
        """Generate a suggested edit for a reference site."""
        if self._llm_fn is not None:
            try:
                suggested = self._llm_fn(file, str(line), symbol, context)
            except Exception as exc:
                suggested = f"[error: {exc}]"
        else:
            suggested = f"# Update call to {symbol} (see change: {context[:60]})"

        return RippleEdit(
            file=file,
            line=line,
            original="",  # would require file read; left empty for stub
            suggested=suggested,
            reason=f"Symbol '{symbol}' was changed",
            symbol=symbol,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_source_line(self, diff: str, symbol: str) -> str:
        for line in diff.splitlines():
            if symbol in line and (line.startswith("+") or line.startswith("-")):
                return line
        return ""

    def _extract_source_file(self, diff: str) -> str:
        for line in diff.splitlines():
            if line.startswith("--- ") or line.startswith("+++ "):
                path = line[4:].strip()
                if path and path != "/dev/null":
                    return path.lstrip("ab/")
        return "<unknown>"
