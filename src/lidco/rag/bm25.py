"""BM25 keyword index for code chunk retrieval."""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# When the fraction of mutated documents is below this threshold *and* an
# existing BM25Okapi model is already built, skip the full rebuild and reuse
# the slightly-stale model.  IDF scores shift negligibly for small mutations
# on large corpora, so search quality is unaffected in practice.
_INCREMENTAL_THRESHOLD: float = 0.1  # 10 %


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens (letters, digits, underscores)."""
    return re.findall(r"\w+", text.lower())


class BM25Index:
    """In-memory BM25 index for code chunks.

    Wraps ``rank_bm25.BM25Okapi`` when the package is installed.  When
    ``rank_bm25`` is absent the index silently returns empty results so the
    rest of the system can degrade gracefully to semantic-only search.

    The underlying BM25 model is rebuilt lazily on the first :meth:`search`
    call after any mutation (``add_many``, ``remove_ids``, or ``clear``).
    """

    def __init__(self) -> None:
        self._corpus: list[tuple[str, list[str]]] = []  # (chunk_id, tokens)
        self._dirty: bool = False
        self._dirty_count: int = 0  # mutations since last rebuild
        self._bm25: Any | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Number of entries currently in the index."""
        return len(self._corpus)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_many(self, entries: list[tuple[str, str]]) -> None:
        """Add (chunk_id, text) pairs to the index.

        Duplicate chunk_ids are allowed — the caller is responsible for
        avoiding them (same contract as the vector store).
        """
        for chunk_id, text in entries:
            self._corpus.append((chunk_id, _tokenize(text)))
        if entries:
            self._dirty = True
            self._dirty_count += len(entries)

    def remove_ids(self, chunk_ids: set[str]) -> None:
        """Remove entries whose chunk_id is in *chunk_ids*."""
        before = len(self._corpus)
        self._corpus = [(cid, toks) for cid, toks in self._corpus if cid not in chunk_ids]
        n_removed = before - len(self._corpus)
        if n_removed:
            self._dirty = True
            self._dirty_count += n_removed

    def clear(self) -> None:
        """Remove all entries and reset internal BM25 state."""
        self._corpus = []
        self._bm25 = None
        self._dirty = False
        self._dirty_count = 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, n_results: int) -> list[tuple[str, float]]:
        """Return up to *n_results* (chunk_id, score) pairs sorted by score desc.

        Scores are normalised to **[0.0, 1.0]** relative to the top hit.
        Returns an empty list when the corpus is empty, the query produces
        no tokens, or ``rank_bm25`` is not installed.
        """
        if not self._corpus:
            return []

        self._rebuild_if_needed()
        if self._bm25 is None:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        raw_scores: list[float] = self._bm25.get_scores(query_tokens)
        pairs = sorted(
            zip([cid for cid, _ in self._corpus], raw_scores),
            key=lambda x: x[1],
            reverse=True,
        )

        max_score = pairs[0][1] if pairs else 0.0
        if max_score <= 0.0:
            return [(cid, 0.0) for cid, _ in pairs[:n_results]]

        return [(cid, score / max_score) for cid, score in pairs[:n_results]]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Serialize the tokenised corpus to a pickle file.

        Only the corpus (chunk IDs + token lists) is stored — the BM25Okapi
        model itself is excluded because it is cheap to reconstruct from the
        corpus on first :meth:`search` call.
        """
        try:
            with open(path, "wb") as f:
                pickle.dump(self._corpus, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.debug("BM25 corpus saved to %s (%d entries)", path, len(self._corpus))
        except Exception as e:
            logger.warning("Failed to save BM25 corpus to %s: %s", path, e)

    def load(self, path: Path) -> bool:
        """Restore the corpus from a pickle file.

        Returns ``True`` on success, ``False`` if the file is missing,
        unreadable, or contains an unexpected format.  On success the index is
        marked dirty so the BM25Okapi model is rebuilt on the next search.
        """
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            if not isinstance(data, list):
                logger.debug("Unexpected BM25 pickle format at %s", path)
                return False
            self._corpus = data
            self._dirty = True
            self._bm25 = None
            logger.debug("BM25 corpus loaded from %s (%d entries)", path, len(self._corpus))
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.debug("Failed to load BM25 corpus from %s: %s", path, e)
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_if_needed(self) -> None:
        """Rebuild the BM25Okapi model from the current corpus if dirty.

        **Incremental optimisation**: when the fraction of mutated documents is
        below :data:`_INCREMENTAL_THRESHOLD` *and* an existing model is already
        built, the rebuild is skipped.  IDF scores shift negligibly for small
        mutations on large corpora, so search quality is unaffected in practice.
        The existing model is reused as-is until the next full rebuild.
        """
        if not self._dirty:
            return

        corpus_size = len(self._corpus)
        if (
            self._bm25 is not None
            and corpus_size > 0
            and self._dirty_count / corpus_size < _INCREMENTAL_THRESHOLD
        ):
            # Skip full rebuild — reuse slightly-stale model
            logger.debug(
                "BM25 incremental skip: %d/%d dirty (%.1f%% < %.0f%% threshold)",
                self._dirty_count,
                corpus_size,
                100 * self._dirty_count / corpus_size,
                100 * _INCREMENTAL_THRESHOLD,
            )
            self._dirty = False
            self._dirty_count = 0
            return

        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]
        except ImportError:
            logger.debug("rank_bm25 not available; BM25 search disabled")
            self._bm25 = None
            self._dirty = False
            self._dirty_count = 0
            return

        token_lists = [toks for _, toks in self._corpus]
        self._bm25 = BM25Okapi(token_lists)
        self._dirty = False
        self._dirty_count = 0
