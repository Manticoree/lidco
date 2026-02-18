"""ChromaDB vector store for code chunk storage and retrieval."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lidco.rag.indexer import CodeChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "lidco_code"


@dataclass(frozen=True)
class SearchResult:
    """A single search result with relevance scoring."""

    chunk: CodeChunk
    score: float
    distance: float


class VectorStore:
    """ChromaDB-backed vector store for code chunks.

    Uses ChromaDB's built-in embedding function (default all-MiniLM-L6-v2)
    for embedding code content and performing similarity search.
    """

    def __init__(self, persist_dir: Path) -> None:
        self._persist_dir = persist_dir
        self._client: Any = None
        self._collection: Any = None
        self._init_chromadb()

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "chromadb is required for RAG functionality. "
                "Install it with: pip install chromadb"
            ) from e

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore initialized at %s (%d documents)",
            self._persist_dir,
            self._collection.count(),
        )

    @staticmethod
    def _chunk_id(chunk: CodeChunk) -> str:
        """Generate a deterministic ID for a chunk based on file path and lines."""
        raw = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add code chunks to the vector store.

        Existing chunks with the same ID are upserted (updated).
        ChromaDB has a batch-size limit, so chunks are added in batches.
        """
        if not chunks:
            return

        batch_size = 500
        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start:batch_start + batch_size]

            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict[str, Any]] = []

            for chunk in batch:
                chunk_id = self._chunk_id(chunk)
                ids.append(chunk_id)
                documents.append(chunk.content)
                metadatas.append({
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "chunk_type": chunk.chunk_type,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "name": chunk.name,
                })

            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

        logger.info("Added %d chunks to vector store", len(chunks))

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_language: str | None = None,
    ) -> list[SearchResult]:
        """Search the vector store for chunks matching a query.

        Returns results ordered by relevance (highest score first).
        """
        if self._collection.count() == 0:
            return []

        where_filter: dict[str, str] | None = None
        if filter_language:
            where_filter = {"language": filter_language}

        # Clamp n_results to the number of documents in the collection
        effective_n = min(n_results, self._collection.count())

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=effective_n,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("Vector search failed: %s", e)
            return []

        search_results: list[SearchResult] = []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            chunk = CodeChunk(
                file_path=meta.get("file_path", ""),
                content=doc,
                language=meta.get("language", "unknown"),
                chunk_type=meta.get("chunk_type", "block"),
                start_line=int(meta.get("start_line", 0)),
                end_line=int(meta.get("end_line", 0)),
                name=meta.get("name", ""),
            )
            # Cosine distance -> similarity score (1.0 = identical, 0.0 = orthogonal)
            score = max(0.0, 1.0 - dist)
            search_results.append(SearchResult(
                chunk=chunk,
                score=score,
                distance=dist,
            ))

        return search_results

    def remove_by_file(self, file_path: str) -> int:
        """Remove all chunks belonging to a specific file.

        Returns the number of chunks removed.
        """
        try:
            existing = self._collection.get(
                where={"file_path": file_path},
                include=[],
            )
            ids_to_remove = existing.get("ids", [])
            if ids_to_remove:
                self._collection.delete(ids=ids_to_remove)
            return len(ids_to_remove)
        except Exception as e:
            logger.warning("Failed to remove chunks for %s: %s", file_path, e)
            return 0

    def clear(self) -> None:
        """Delete all chunks and recreate the collection."""
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # Collection may not exist
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about the vector store."""
        count = self._collection.count()

        stats: dict[str, Any] = {
            "total_chunks": count,
            "persist_dir": str(self._persist_dir),
            "collection_name": COLLECTION_NAME,
        }

        if count == 0:
            stats["languages"] = []
            return stats

        # Sample metadata to gather language stats
        try:
            sample_size = min(count, 10000)
            sample = self._collection.get(
                limit=sample_size,
                include=["metadatas"],
            )
            metas = sample.get("metadatas", [])
            languages: set[str] = set()
            files: set[str] = set()
            for meta in metas:
                lang = meta.get("language")
                if lang:
                    languages.add(lang)
                fp = meta.get("file_path")
                if fp:
                    files.add(fp)

            stats["languages"] = sorted(languages)
            stats["unique_files"] = len(files)
        except Exception as e:
            logger.warning("Failed to gather stats: %s", e)
            stats["languages"] = []

        return stats
