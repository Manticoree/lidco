"""Auto-apply PR review suggestions (GitHub Copilot Code Review parity)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Suggestion:
    file: str
    description: str
    old_code: str       # text to replace (may be empty = append)
    new_code: str       # replacement text
    line_hint: int = 0  # approximate line number (0 = unknown)
    source: str = ""    # original review text that generated this suggestion


@dataclass
class ApplyResult:
    suggestion: Suggestion
    success: bool
    message: str


@dataclass
class ApplyBatch:
    results: list[ApplyResult]
    applied: int
    failed: int
    skipped: int

    @property
    def success_rate(self) -> float:
        total = self.applied + self.failed
        return self.applied / total if total > 0 else 0.0

    def format_summary(self) -> str:
        lines = [f"Applied {self.applied}/{self.applied + self.failed} suggestions"]
        for r in self.results:
            icon = "v" if r.success else "x"
            lines.append(f"  {icon} {r.suggestion.file}: {r.message}")
        return "\n".join(lines)


# Regex to capture suggestion blocks in review text
# Matches: ```suggestion\n...\n``` fenced blocks with optional file/line hints
_SUGGESTION_BLOCK = re.compile(
    r"(?:in\s+`?(?P<file>[\w/.\-]+)`?.*?(?:line\s+(?P<line>\d+))?.*?\n)?"
    r"```suggestion\n(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_FILE_REF = re.compile(r"`(?P<file>[\w/.\-]+\.\w+)`")


class SuggestionApplier:
    """Parse review text for code suggestions and apply them to files."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()

    def parse_suggestions(self, review_text: str) -> list[Suggestion]:
        """Extract Suggestion objects from review/comment text."""
        suggestions: list[Suggestion] = []
        # Find all suggestion blocks
        for m in _SUGGESTION_BLOCK.finditer(review_text):
            file_hint = m.group("file") or ""
            line_hint = int(m.group("line") or 0)
            new_code = m.group("code").strip()
            context_before = review_text[max(0, m.start() - 200):m.start()]
            # Try to extract file from context
            if not file_hint:
                fm = _FILE_REF.search(context_before)
                if fm:
                    file_hint = fm.group("file")
            # Extract old code from context (look for ```old or the word "replace")
            old_code = ""
            old_match = re.search(r"```(?:old|python|py)\n(.*?)```", context_before, re.DOTALL)
            if old_match:
                old_code = old_match.group(1).strip()
            suggestions.append(Suggestion(
                file=file_hint,
                description=context_before.strip()[-80:],
                old_code=old_code,
                new_code=new_code,
                line_hint=line_hint,
                source=m.group(0)[:120],
            ))
        return suggestions

    def apply(self, suggestion: Suggestion, *, dry_run: bool = False) -> ApplyResult:
        """Apply a single suggestion to the target file."""
        if not suggestion.file:
            return ApplyResult(suggestion=suggestion, success=False, message="No target file specified")

        path = self.repo_root / suggestion.file
        if not path.exists():
            return ApplyResult(suggestion=suggestion, success=False, message=f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ApplyResult(suggestion=suggestion, success=False, message=str(e))

        if suggestion.old_code and suggestion.old_code in content:
            new_content = content.replace(suggestion.old_code, suggestion.new_code, 1)
            if not dry_run:
                path.write_text(new_content, encoding="utf-8")
            return ApplyResult(suggestion=suggestion, success=True, message=f"Replaced in {suggestion.file}")
        elif not suggestion.old_code and suggestion.new_code:
            # Append mode
            new_content = content + "\n" + suggestion.new_code
            if not dry_run:
                path.write_text(new_content, encoding="utf-8")
            return ApplyResult(suggestion=suggestion, success=True, message=f"Appended to {suggestion.file}")
        else:
            return ApplyResult(suggestion=suggestion, success=False, message="old_code not found in file")

    def apply_all(
        self,
        suggestions: list[Suggestion],
        *,
        dry_run: bool = False,
    ) -> ApplyBatch:
        """Apply all suggestions, returning a batch result."""
        results: list[ApplyResult] = []
        applied = 0
        failed = 0
        skipped = 0
        for s in suggestions:
            if not s.file:
                results.append(ApplyResult(suggestion=s, success=False, message="skipped (no file)"))
                skipped += 1
                continue
            r = self.apply(s, dry_run=dry_run)
            results.append(r)
            if r.success:
                applied += 1
            else:
                failed += 1
        return ApplyBatch(results=results, applied=applied, failed=failed, skipped=skipped)
