"""KnowledgeBase — query-based document retrieval from Notion pages."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class KBDocument:
    """A document stored in the knowledge base."""

    title: str
    content: str
    tokens: list[str] = field(default_factory=list)


class KnowledgeBase:
    """Simple keyword-based knowledge base over documents.

    Documents are indexed by lowercased word tokens extracted from title
    and content.  The :meth:`query` method returns documents whose tokens
    overlap with the query tokens, ranked by overlap count.
    """

    def __init__(self) -> None:
        self._docs: list[KBDocument] = []
        self._index: dict[str, list[int]] = {}  # token -> doc indices

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    # ---------------------------------------------------------- mutators

    def add_doc(self, title: str, content: str) -> None:
        """Add a document to the knowledge base.

        Raises
        ------
        ValueError
            If *title* is empty.
        """
        if not title.strip():
            raise ValueError("Title must not be empty")
        tokens = list(dict.fromkeys(self._tokenize(title + " " + content)))
        doc = KBDocument(title=title, content=content, tokens=tokens)
        idx = len(self._docs)
        self._docs.append(doc)
        for tok in tokens:
            self._index.setdefault(tok, []).append(idx)

    # ---------------------------------------------------------- queries

    def query(self, question: str) -> list[KBDocument]:
        """Return documents relevant to *question*, best-match first.

        Relevance is measured by number of overlapping tokens.
        """
        q_tokens = set(self._tokenize(question))
        if not q_tokens:
            return []
        # score each document by overlap
        scores: dict[int, int] = {}
        for tok in q_tokens:
            for idx in self._index.get(tok, []):
                scores[idx] = scores.get(idx, 0) + 1
        ranked = sorted(scores, key=lambda i: scores[i], reverse=True)
        return [self._docs[i] for i in ranked]

    def inject_context(self, question: str, max_tokens: int = 500) -> str:
        """Build a context string from the most relevant documents.

        Concatenates document content (most relevant first) until
        *max_tokens* approximate word-tokens are reached.

        Parameters
        ----------
        question:
            The user question to match against.
        max_tokens:
            Maximum approximate token budget (word count).
        """
        docs = self.query(question)
        parts: list[str] = []
        used = 0
        for doc in docs:
            words = doc.content.split()
            if used + len(words) > max_tokens and parts:
                break
            parts.append(f"## {doc.title}\n{doc.content}")
            used += len(words)
        return "\n\n".join(parts)

    def index_size(self) -> int:
        """Return the number of indexed documents."""
        return len(self._docs)
