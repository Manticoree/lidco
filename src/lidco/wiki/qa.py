"""CodebaseQA — natural language Q&A against indexed code and wiki.

Strategy:
1. BM25 keyword search across source files + wiki pages
2. Optional LLM synthesis with citations
3. Fallback: grep-based search if index is empty
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QAAnswer:
    answer: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0


_SOURCE_EXTENSIONS = frozenset({".py", ".ts", ".js", ".go", ".rs", ".md"})

# Directories to skip during search
_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build",
})


class CodebaseQA:
    """Answers questions about the codebase using search + optional LLM."""

    def __init__(
        self,
        llm_client: Any | None = None,
        max_sources: int = 5,
        max_context_chars: int = 6000,
    ) -> None:
        self._llm = llm_client
        self._max_sources = max_sources
        self._max_context_chars = max_context_chars

    def ask(self, question: str, project_dir: Path) -> QAAnswer:
        """Answer *question* about the codebase rooted at *project_dir*."""
        candidates = self._search(question, project_dir)
        if not candidates:
            return QAAnswer(
                answer="No relevant code found for that question.",
                sources=[],
                confidence=0.0,
            )

        sources = [path for path, _ in candidates[: self._max_sources]]
        context = self._build_context(candidates)

        if self._llm:
            return self._llm_answer(question, context, sources)

        return self._heuristic_answer(question, context, sources)

    # ------------------------------------------------------------------

    def _search(self, question: str, project_dir: Path) -> list[tuple[str, float]]:
        """BM25-like keyword search across source files and wiki."""
        keywords = self._extract_keywords(question)
        if not keywords:
            return []

        scores: dict[str, float] = {}
        for p in self._iter_files(project_dir):
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            content_lower = content.lower()
            score = sum(
                content_lower.count(kw.lower()) * (2 if kw in content else 1)
                for kw in keywords
            )
            if score > 0:
                scores[str(p)] = float(score)

        sorted_paths = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_paths[: self._max_sources * 2]

    def _iter_files(self, project_dir: Path):
        wiki_dir = project_dir / ".lidco" / "wiki"
        for p in project_dir.rglob("*"):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS or part.startswith(".") for part in p.parts):
                continue
            if p.suffix in _SOURCE_EXTENSIONS:
                yield p
        # Also include wiki pages
        if wiki_dir.exists():
            for p in wiki_dir.glob("*.md"):
                yield p

    def _extract_keywords(self, question: str) -> list[str]:
        stop = {"what", "how", "does", "is", "the", "a", "an", "in", "to", "of", "do", "where"}
        words = re.findall(r"[a-zA-Z_][a-zA-Z_0-9]+", question.lower())
        return [w for w in words if w not in stop and len(w) >= 3]

    def _build_context(self, candidates: list[tuple[str, float]]) -> str:
        parts: list[str] = []
        total = 0
        for path, score in candidates[: self._max_sources]:
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                excerpt = content[: self._max_context_chars // self._max_sources]
                parts.append(f"### {path}\n{excerpt}")
                total += len(excerpt)
                if total >= self._max_context_chars:
                    break
            except OSError:
                pass
        return "\n\n".join(parts)

    def _heuristic_answer(
        self,
        question: str,
        context: str,
        sources: list[str],
    ) -> QAAnswer:
        keywords = self._extract_keywords(question)
        # Extract sentences containing keywords from context
        sentences = re.split(r"[.!?\n]", context)
        relevant = [
            s.strip() for s in sentences
            if any(kw.lower() in s.lower() for kw in keywords) and len(s.strip()) > 20
        ]
        answer_parts = relevant[:5] if relevant else ["See the source files listed below."]
        answer = ". ".join(answer_parts[:3]).strip()
        return QAAnswer(
            answer=answer or "Relevant code found — check the source files.",
            sources=sources,
            confidence=0.5,
        )

    def _llm_answer(
        self,
        question: str,
        context: str,
        sources: list[str],
    ) -> QAAnswer:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a code assistant.  Answer the question concisely based on the "
                    "provided code context.  Cite specific files and functions."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nCode context:\n{context[:self._max_context_chars]}",
            },
        ]
        try:
            answer = self._llm(messages).strip()
            return QAAnswer(answer=answer, sources=sources, confidence=0.85)
        except Exception:
            return self._heuristic_answer(question, context, sources)
