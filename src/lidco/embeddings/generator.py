"""Embedding generator that chunks code files and produces vector embeddings."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodeChunk:
    """A chunk of code extracted from a file."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: str  # "function" | "class" | "block"
    name: str | None = None


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for code chunking."""

    chunk_size: int = 500  # chars
    chunk_overlap: int = 50
    respect_boundaries: bool = True


_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
        "for", "of", "and", "or", "not", "this", "that", "it", "with", "from",
        "by", "as", "be", "has", "have", "had", "do", "does", "did", "will",
        "would", "can", "could", "should", "may", "might", "shall",
    }
)

_MAX_VOCAB_SIZE = 10000

_BOUNDARY_RE = re.compile(r"^(def |class )", re.MULTILINE)


class EmbeddingGenerator:
    """Generate TF-IDF based embeddings for code chunks."""

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        provider: str = "tfidf",
    ) -> None:
        self.config = config or ChunkingConfig()
        self.provider = provider
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._doc_count: int = 0

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Split *content* into chunks respecting function/class boundaries."""
        if not content:
            return []

        lines = content.split("\n")

        if self.config.respect_boundaries:
            chunks = self._chunk_by_boundaries(file_path, lines)
            if chunks:
                return chunks

        # Fallback: size-based chunking
        return self._chunk_by_size(file_path, content, lines)

    def _chunk_by_boundaries(
        self, file_path: str, lines: list[str]
    ) -> list[CodeChunk]:
        boundaries: list[tuple[int, str, str]] = []  # (line_idx, type, name)
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("def "):
                name = stripped[4:].split("(")[0].split(":")[0].strip()
                boundaries.append((idx, "function", name))
            elif stripped.startswith("class "):
                name = stripped[6:].split("(")[0].split(":")[0].strip()
                boundaries.append((idx, "class", name))

        if not boundaries:
            return []

        chunks: list[CodeChunk] = []
        for i, (start, ctype, name) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(lines)
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end,
                    content=chunk_content,
                    chunk_type=ctype,
                    name=name,
                )
            )
        return chunks

    def _chunk_by_size(
        self, file_path: str, content: str, lines: list[str]
    ) -> list[CodeChunk]:
        cfg = self.config
        chunks: list[CodeChunk] = []
        pos = 0
        while pos < len(content):
            end_pos = min(pos + cfg.chunk_size, len(content))
            chunk_text = content[pos:end_pos]

            # Map char positions to line numbers
            start_line = content[:pos].count("\n") + 1
            end_line = content[:end_pos].count("\n") + 1

            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    content=chunk_text,
                    chunk_type="block",
                    name=None,
                )
            )
            step = max(1, cfg.chunk_size - cfg.chunk_overlap)
            pos += step

        return chunks

    # ------------------------------------------------------------------
    # Tokenization & Vocabulary
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]

    def build_vocabulary(self, texts: list[str]) -> None:
        """Build TF-IDF vocabulary from a corpus of texts."""
        doc_freq: dict[str, int] = {}
        self._doc_count = len(texts)

        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        # Sort by frequency descending, take top MAX_VOCAB_SIZE
        sorted_terms = sorted(doc_freq.items(), key=lambda x: x[1], reverse=True)
        sorted_terms = sorted_terms[:_MAX_VOCAB_SIZE]

        self._vocab = {term: idx for idx, (term, _) in enumerate(sorted_terms)}

        # Compute IDF
        n = max(self._doc_count, 1)
        self._idf = {
            term: math.log((n + 1) / (df + 1)) + 1
            for term, df in doc_freq.items()
            if term in self._vocab
        }

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def generate_embedding(self, text: str) -> list[float]:
        """Generate a TF-IDF embedding vector for *text*."""
        if not self._vocab:
            # Auto-build vocab from this single text
            self.build_vocabulary([text])

        tokens = self._tokenize(text)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        total = max(len(tokens), 1)
        dim = len(self._vocab)
        vec = [0.0] * dim

        for term, count in tf.items():
            if term in self._vocab:
                idx = self._vocab[term]
                idf = self._idf.get(term, 1.0)
                vec[idx] = (count / total) * idf

        # Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def embed_chunks(
        self, chunks: list[CodeChunk]
    ) -> list[tuple[CodeChunk, list[float]]]:
        """Generate embeddings for all chunks."""
        return [(chunk, self.generate_embedding(chunk.content)) for chunk in chunks]
