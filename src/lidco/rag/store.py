"""ChromaDB vector store for code chunk storage and retrieval."""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lidco.rag.bm25 import BM25Index
from lidco.rag.indexer import CodeChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "lidco_code"


@dataclass(frozen=True)
class SearchResult:
    """A single search result with relevance scoring."""

    chunk: CodeChunk
    score: float
    distance: float


def _reciprocal_rank_fusion(
    semantic_results: list[SearchResult],
    bm25_results: list[SearchResult],
    bm25_weight: float = 0.4,
    k: int = 60,
) -> list[SearchResult]:
    """Merge two ranked result lists using Reciprocal Rank Fusion (RRF).

    Each result is scored as::

        rrf(d) = semantic_weight / (k + semantic_rank(d) + 1)
               + bm25_weight    / (k + bm25_rank(d)     + 1)

    where *k* = 60 is the standard smoothing constant.  Results that appear
    in both lists receive contributions from both terms, naturally boosting
    chunks that are relevant according to both retrieval methods.
    """
    def _chunk_key(r: SearchResult) -> str:
        return f"{r.chunk.file_path}:{r.chunk.start_line}"

    semantic_weight = 1.0 - bm25_weight

    all_results: dict[str, SearchResult] = {}
    rrf_scores: dict[str, float] = {}

    for rank, result in enumerate(semantic_results):
        key = _chunk_key(result)
        all_results[key] = result
        rrf_scores[key] = rrf_scores.get(key, 0.0) + semantic_weight / (k + rank + 1)

    for rank, result in enumerate(bm25_results):
        key = _chunk_key(result)
        if key not in all_results:
            all_results[key] = result
        rrf_scores[key] = rrf_scores.get(key, 0.0) + bm25_weight / (k + rank + 1)

    sorted_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    return [all_results[key] for key in sorted_keys]


class VectorStore:
    """ChromaDB-backed vector store for code chunks.

    Uses ChromaDB's built-in embedding function (default all-MiniLM-L6-v2)
    for embedding code content and performing similarity search.

    A companion :class:`~lidco.rag.bm25.BM25Index` is maintained in memory
    for keyword-based retrieval.  :meth:`search_hybrid` merges both ranking
    lists via Reciprocal Rank Fusion for better precision on exact symbol
    names and identifiers.
    """

    def __init__(self, persist_dir: Path) -> None:
        self._persist_dir = persist_dir
        self._client: Any = None
        self._collection: Any = None
        self._bm25: BM25Index = BM25Index()
        # chunk_id -> CodeChunk — populated alongside ChromaDB, used to
        # reconstruct SearchResult objects for BM25-only hits.
        self._chunk_cache: dict[str, CodeChunk] = {}
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
        count = self._collection.count()
        logger.info(
            "VectorStore initialized at %s (%d documents)",
            self._persist_dir,
            count,
        )
        if count > 0:
            if not self._try_load_bm25_cache(count):
                self._rebuild_bm25_from_collection()

    # ── BM25 cache persistence ────────────────────────────────────────────────

    @property
    def _bm25_cache_path(self) -> Path:
        """Path to the pickle file used to persist the BM25 corpus."""
        return self._persist_dir / "bm25_cache.pkl"

    def _try_load_bm25_cache(self, collection_count: int) -> bool:
        """Attempt to restore BM25 state from the on-disk pickle cache.

        The cache is considered valid only when the recorded document count
        matches the current ChromaDB collection count.  If the counts diverge
        (chunks were added or deleted while the process was not running), the
        caller falls back to a full rebuild.

        Returns ``True`` when the cache was loaded successfully.
        """
        pkl = self._bm25_cache_path
        if not pkl.exists():
            return False
        try:
            with open(pkl, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, dict) or data.get("count") != collection_count:
                logger.debug("BM25 cache count mismatch — will rebuild")
                return False
            chunk_cache: dict[str, Any] = data.get("chunk_cache", {})
            corpus_path = data.get("corpus_path")
            if corpus_path and Path(corpus_path).exists():
                if not self._bm25.load(Path(corpus_path)):
                    return False
            else:
                return False
            self._chunk_cache = chunk_cache
            logger.info(
                "BM25 index restored from cache (%d entries, %d chunks cached)",
                self._bm25.size,
                len(self._chunk_cache),
            )
            return True
        except Exception as e:
            logger.debug("BM25 cache load failed: %s", e)
            return False

    def _save_bm25_cache(self) -> None:
        """Persist the BM25 corpus and chunk cache to disk.

        Called after every mutation so the next process startup skips the
        O(N) ChromaDB rebuild.  Failures are logged but never raised — a
        missing cache simply triggers a rebuild on the next start.
        """
        corpus_path = self._persist_dir / "bm25_corpus.pkl"
        self._bm25.save(corpus_path)
        meta = {
            "count": self._collection.count(),
            "chunk_cache": self._chunk_cache,
            "corpus_path": str(corpus_path),
        }
        try:
            with open(self._bm25_cache_path, "wb") as f:
                pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.debug("BM25 cache saved (%d docs)", meta["count"])
        except Exception as e:
            logger.warning("Failed to save BM25 cache metadata: %s", e)

    def _invalidate_bm25_cache(self) -> None:
        """Delete on-disk BM25 cache files."""
        for p in (self._bm25_cache_path, self._persist_dir / "bm25_corpus.pkl"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

    def _rebuild_bm25_from_collection(self) -> None:
        """Rebuild BM25 index and chunk cache from existing ChromaDB data.

        Called once after connecting to a non-empty persistent collection so
        that BM25 search works correctly across process restarts.

        Uses ID-based pagination to guarantee all chunks are loaded in a
        deterministic order regardless of collection size.
        """
        try:
            # Fetch all IDs first (lightweight — no documents returned)
            id_data = self._collection.get(include=[])
            all_ids: list[str] = id_data.get("ids", [])
        except Exception as e:
            logger.warning("Failed to fetch chunk IDs for BM25 rebuild: %s", e)
            return

        if not all_ids:
            return

        _BATCH_SIZE = 5_000
        entries: list[tuple[str, str]] = []

        for batch_start in range(0, len(all_ids), _BATCH_SIZE):
            batch_ids = all_ids[batch_start : batch_start + _BATCH_SIZE]
            try:
                data = self._collection.get(
                    ids=batch_ids,
                    include=["documents", "metadatas"],
                )
            except Exception as e:
                logger.warning(
                    "Failed to load BM25 rebuild batch %d–%d: %s",
                    batch_start,
                    batch_start + len(batch_ids),
                    e,
                )
                continue

            ids: list[str] = data.get("ids", [])
            documents: list[str] = data.get("documents", [])
            metadatas: list[dict[str, Any]] = data.get("metadatas", [])

            for chunk_id, doc, meta in zip(ids, documents, metadatas):
                chunk = CodeChunk(
                    file_path=meta.get("file_path", ""),
                    content=doc,
                    language=meta.get("language", "unknown"),
                    chunk_type=meta.get("chunk_type", "block"),
                    start_line=int(meta.get("start_line", 0)),
                    end_line=int(meta.get("end_line", 0)),
                    name=meta.get("name", ""),
                )
                self._chunk_cache[chunk_id] = chunk
                entries.append((chunk_id, doc))

        self._bm25.add_many(entries)
        logger.info("Rebuilt BM25 index from %d existing chunks", len(entries))

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
            bm25_entries: list[tuple[str, str]] = []

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
                self._chunk_cache[chunk_id] = chunk
                bm25_entries.append((chunk_id, chunk.content))

            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            # Remove before add so repeated upserts don't accumulate duplicates
            # in the BM25 corpus (ChromaDB handles this natively; BM25 is a list).
            self._bm25.remove_ids(set(ids))
            self._bm25.add_many(bm25_entries)

        logger.info("Added %d chunks to vector store", len(chunks))
        self._save_bm25_cache()

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_language: str | None = None,
        path_prefix: str | None = None,
    ) -> list[SearchResult]:
        """Search the vector store for chunks matching a query.

        When *path_prefix* is set, only chunks whose ``file_path`` starts with
        that prefix are returned.  To compensate for the reduced candidate pool
        the underlying ChromaDB query overfetches by a factor of 5.

        Returns results ordered by relevance (highest score first).
        """
        if self._collection.count() == 0:
            return []

        where_filter: dict[str, str] | None = None
        if filter_language:
            where_filter = {"language": filter_language}

        # Overfetch when path_prefix is set to account for filtering loss
        fetch_n = n_results * 5 if path_prefix else n_results
        # Clamp to the number of documents in the collection
        effective_n = min(fetch_n, self._collection.count())

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
            file_path = meta.get("file_path", "")
            if path_prefix and not file_path.startswith(path_prefix):
                continue
            chunk = CodeChunk(
                file_path=file_path,
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

        return search_results[:n_results]

    def search_hybrid(
        self,
        query: str,
        n_results: int = 10,
        filter_language: str | None = None,
        path_prefix: str | None = None,
        bm25_weight: float = 0.4,
    ) -> list[SearchResult]:
        """Hybrid semantic + BM25 search with Reciprocal Rank Fusion.

        Fetches ``n_results * 3`` candidates from each retriever, merges the
        two ranked lists via :func:`_reciprocal_rank_fusion`, and returns the
        top *n_results* items.

        When *path_prefix* is provided, only chunks whose ``file_path`` starts
        with that prefix are included in the final results.

        Falls back to semantic-only results when the BM25 index is empty
        (e.g. the project has never been indexed, or ``rank_bm25`` is not
        installed).
        """
        candidates = n_results * 3
        semantic_results = self.search(
            query, n_results=candidates,
            filter_language=filter_language,
            path_prefix=path_prefix,
        )

        # BM25 search returns (chunk_id, normalised_score) pairs
        bm25_hits = self._bm25.search(query, n_results=candidates)
        if not bm25_hits:
            return semantic_results[:n_results]

        # Reconstruct SearchResult objects for BM25 hits
        bm25_results: list[SearchResult] = []
        for chunk_id, bm25_score in bm25_hits:
            chunk = self._chunk_cache.get(chunk_id)
            if chunk is None:
                continue
            if filter_language and chunk.language != filter_language:
                continue
            if path_prefix and not chunk.file_path.startswith(path_prefix):
                continue
            bm25_results.append(SearchResult(
                chunk=chunk,
                score=bm25_score,
                distance=max(0.0, 1.0 - bm25_score),
            ))

        if not bm25_results:
            return semantic_results[:n_results]

        merged = _reciprocal_rank_fusion(
            semantic_results, bm25_results, bm25_weight=bm25_weight
        )
        return merged[:n_results]

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
                self._bm25.remove_ids(set(ids_to_remove))
                for cid in ids_to_remove:
                    self._chunk_cache.pop(cid, None)
                self._save_bm25_cache()
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
        self._bm25.clear()
        self._chunk_cache.clear()
        self._invalidate_bm25_cache()
        logger.info("Vector store cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about the vector store."""
        count = self._collection.count()

        stats: dict[str, Any] = {
            "total_chunks": count,
            "persist_dir": str(self._persist_dir),
            "collection_name": COLLECTION_NAME,
            "bm25_index_size": self._bm25.size,
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
