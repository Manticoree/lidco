"""Automatically inject relevant code snippets as context for user prompts."""

from __future__ import annotations

from dataclasses import dataclass

from lidco.embeddings.retriever import HybridRetriever


@dataclass(frozen=True)
class ContextSnippet:
    """A relevant code snippet for context injection."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    relevance_score: float
    reason: str


@dataclass(frozen=True)
class InjectionConfig:
    """Configuration for auto-context injection."""

    enabled: bool = True
    max_snippets: int = 5
    max_tokens: int = 2000
    min_relevance: float = 0.1


class AutoContextInjector:
    """Automatically inject relevant code snippets as context."""

    def __init__(
        self,
        retriever: HybridRetriever,
        config: InjectionConfig | None = None,
    ) -> None:
        self.retriever = retriever
        self.config = config or InjectionConfig()

    def get_context(
        self,
        user_prompt: str,
        explicit_files: list[str] | None = None,
    ) -> list[ContextSnippet]:
        """Retrieve relevant context snippets for a user prompt."""
        if not self.config.enabled:
            return []

        if explicit_files is not None and len(explicit_files) > 0:
            return []

        results = self.retriever.search(user_prompt, top_k=self.config.max_snippets * 2)

        snippets: list[ContextSnippet] = []
        total_tokens = 0

        for result in results:
            if result.score < self.config.min_relevance:
                continue

            tokens = self.estimate_tokens(result.content)
            if total_tokens + tokens > self.config.max_tokens:
                continue

            snippets.append(
                ContextSnippet(
                    file_path=result.file_path,
                    start_line=result.start_line,
                    end_line=result.end_line,
                    content=result.content,
                    relevance_score=result.score,
                    reason=f"Matched via {result.source} search",
                )
            )
            total_tokens += tokens

            if len(snippets) >= self.config.max_snippets:
                break

        return snippets

    def format_context(self, snippets: list[ContextSnippet]) -> str:
        """Format snippets as markdown context block."""
        if not snippets:
            return ""

        parts: list[str] = ["## Relevant Code Context\n"]
        for snippet in snippets:
            header = (
                f"### {snippet.file_path}:{snippet.start_line}-{snippet.end_line}"
                f" (relevance: {snippet.relevance_score:.2f})"
            )
            parts.append(f"{header}\n```\n{snippet.content}\n```\n")

        return "\n".join(parts)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (4 chars per token)."""
        return len(text) // 4
