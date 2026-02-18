"""Context retriever that combines indexing and vector search for RAG."""

from __future__ import annotations

import logging
from pathlib import Path

from lidco.rag.indexer import CodeIndexer
from lidco.rag.store import SearchResult, VectorStore

logger = logging.getLogger(__name__)


class ContextRetriever:
    """High-level interface for the RAG system.

    Combines the CodeIndexer and VectorStore to provide
    project indexing and context retrieval for LLM queries.
    """

    def __init__(
        self,
        store: VectorStore,
        indexer: CodeIndexer,
        project_dir: Path,
    ) -> None:
        self._store = store
        self._indexer = indexer
        self._project_dir = project_dir

    def index_project(self, extensions: set[str] | None = None) -> int:
        """Index the entire project directory.

        Returns the number of chunks indexed.
        """
        target_extensions = extensions or self._indexer.get_supported_extensions()

        logger.info("Indexing project at %s", self._project_dir)
        chunks = self._indexer.index_directory(self._project_dir, target_extensions)

        if not chunks:
            logger.warning("No code chunks found in %s", self._project_dir)
            return 0

        self._store.add_chunks(chunks)
        logger.info("Indexed %d chunks from project", len(chunks))
        return len(chunks)

    def retrieve(
        self,
        query: str,
        max_results: int = 10,
        filter_language: str | None = None,
    ) -> str:
        """Retrieve relevant code context for a query.

        Returns a formatted string suitable for inclusion in an LLM prompt.
        """
        results = self._store.search(
            query=query,
            n_results=max_results,
            filter_language=filter_language,
        )

        if not results:
            return ""

        return _format_results(results)

    def update_file(self, file_path: Path) -> int:
        """Re-index a single file for incremental updates.

        Removes existing chunks for the file, re-indexes it,
        and adds the new chunks to the store.

        Returns the number of new chunks indexed.
        """
        abs_path = file_path if file_path.is_absolute() else self._project_dir / file_path

        if not abs_path.is_file():
            logger.warning("File does not exist, removing from index: %s", abs_path)
            self._store.remove_by_file(str(abs_path))
            return 0

        # Remove old chunks for this file
        removed = self._store.remove_by_file(str(abs_path))
        if removed:
            logger.debug("Removed %d old chunks for %s", removed, abs_path)

        # Re-index the file
        chunks = self._indexer.index_file(abs_path)
        if chunks:
            self._store.add_chunks(chunks)
            logger.info("Updated index for %s: %d chunks", abs_path, len(chunks))

        return len(chunks)

    def get_stats(self) -> dict:
        """Return statistics about the vector store."""
        return self._store.get_stats()

    def clear(self) -> None:
        """Clear the entire vector store."""
        self._store.clear()
        logger.info("RAG index cleared")


def _format_results(results: list[SearchResult]) -> str:
    """Format search results into a string for LLM context injection."""
    sections: list[str] = []
    sections.append("## Relevant Code Context\n")

    for i, result in enumerate(results, 1):
        chunk = result.chunk
        header = f"### {chunk.file_path}:{chunk.start_line} ({chunk.chunk_type}: {chunk.name})"
        sections.append(header)
        sections.append(f"```{chunk.language}")
        sections.append(chunk.content.rstrip())
        sections.append("```\n")

    return "\n".join(sections)
