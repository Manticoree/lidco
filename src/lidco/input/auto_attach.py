"""Auto-attach resolver: match implicit file references in prompts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AttachResult:
    """A matched file with relevance score."""

    path: str
    score: float
    reason: str


# Common implicit references and their file patterns
_IMPLICIT_REFS: list[tuple[re.Pattern[str], list[str], str]] = [
    (re.compile(r"\b(auth|authentication|login|signup|sign[- ]?up)\b", re.I),
     ["auth", "login", "signup", "authentication"],
     "auth reference"),
    (re.compile(r"\b(config|configuration|settings|preferences)\b", re.I),
     ["config", "settings", "preferences", "configuration"],
     "config reference"),
    (re.compile(r"\b(tests?|spec|testing)\b", re.I),
     ["test_", "_test", "spec", "tests/", "test"],
     "test reference"),
    (re.compile(r"\b(route|router|routing|endpoint|api)\b", re.I),
     ["route", "router", "api", "endpoint", "views"],
     "routing reference"),
    (re.compile(r"\b(model|schema|entity|database|db|migration)\b", re.I),
     ["model", "schema", "entity", "migration", "db"],
     "model reference"),
    (re.compile(r"\b(util|utility|helper|utils|helpers)\b", re.I),
     ["util", "helper", "utils", "helpers"],
     "utility reference"),
    (re.compile(r"\b(component|widget|ui|view|template|layout)\b", re.I),
     ["component", "widget", "view", "template", "layout", "ui"],
     "UI reference"),
    (re.compile(r"\b(middleware|interceptor|filter|guard)\b", re.I),
     ["middleware", "interceptor", "filter", "guard"],
     "middleware reference"),
    (re.compile(r"\b(service|provider|manager)\b", re.I),
     ["service", "provider", "manager"],
     "service reference"),
    (re.compile(r"\b(cli|command|commands|cmd)\b", re.I),
     ["cli", "command", "cmd"],
     "CLI reference"),
]


class AutoAttachResolver:
    """Resolves implicit file references in prompts against a project file list."""

    def resolve(
        self,
        prompt: str,
        project_files: list[str],
        token_budget: Optional[int] = None,
    ) -> list[AttachResult]:
        """Analyze prompt for implicit file references and match against project files.

        Args:
            prompt: The user's input text.
            project_files: List of file paths in the project.
            token_budget: Optional max number of files to return (approximating token budget).

        Returns:
            List of AttachResult sorted by score descending.
        """
        if not prompt or not prompt.strip() or not project_files:
            return []

        text = prompt.strip()
        results: dict[str, AttachResult] = {}

        # 1. Check for explicit file references (quoted or path-like)
        explicit_refs = re.findall(r'["\']([^"\']+\.\w+)["\']', text)
        explicit_refs += re.findall(r'\b([\w/\\]+\.\w{1,10})\b', text)

        for ref in explicit_refs:
            ref_lower = ref.lower().replace("\\", "/")
            for fpath in project_files:
                fpath_lower = fpath.lower().replace("\\", "/")
                if ref_lower in fpath_lower or fpath_lower.endswith(ref_lower):
                    if fpath not in results or results[fpath].score < 1.0:
                        results[fpath] = AttachResult(
                            path=fpath,
                            score=1.0,
                            reason=f"explicit reference: {ref}",
                        )

        # 2. Check implicit reference patterns
        for pattern, keywords, reason in _IMPLICIT_REFS:
            if not pattern.search(text):
                continue
            for fpath in project_files:
                fpath_lower = fpath.lower().replace("\\", "/")
                fname = fpath_lower.rsplit("/", 1)[-1] if "/" in fpath_lower else fpath_lower
                best_score = 0.0
                for kw in keywords:
                    if kw.lower() in fpath_lower:
                        score = 0.7
                        # Boost if keyword is in filename (not just path)
                        if kw.lower() in fname:
                            score = 0.85
                        best_score = max(best_score, score)
                if best_score > 0:
                    if fpath not in results or results[fpath].score < best_score:
                        results[fpath] = AttachResult(
                            path=fpath,
                            score=best_score,
                            reason=reason,
                        )

        # Sort by score descending, then by path for stability
        sorted_results = sorted(
            results.values(),
            key=lambda r: (-r.score, r.path),
        )

        # Apply token budget (limit number of files)
        if token_budget is not None and token_budget > 0:
            sorted_results = sorted_results[:token_budget]

        return sorted_results
