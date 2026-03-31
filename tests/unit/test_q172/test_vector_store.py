"""Tests for lidco.embeddings.vector_store."""

from __future__ import annotations

import time
import unittest

from lidco.embeddings.vector_store import VectorEntry, VectorStore


def _make_entry(
    id: str = "e1",
    file_path: str = "a.py",
    start_line: int = 1,
    end_line: int = 10,
    content: str = "hello world",
    chunk_type: str = "function",
    name: str = "foo",
    embedding: list[float] | None = None,
    updated_at: float = 0.0,
) -> VectorEntry:
    return VectorEntry(
        id=id,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        content=content,
        chunk_type=chunk_type,
        name=name,
        embedding=embedding or [1.0, 0.0, 0.0],
        updated_at=updated_at or time.time(),
    )


class TestVectorStoreInit(unittest.TestCase):
    def test_init_creates_table(self) -> None:
        store = VectorStore()
        self.assertEqual(store.count(), 0)
        store.close()


class TestUpsert(unittest.TestCase):
    def test_upsert_and_count(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1"))
        self.assertEqual(store.count(), 1)
        store.upsert(_make_entry(id="e2"))
        self.assertEqual(store.count(), 2)
        store.close()

    def test_upsert_batch(self) -> None:
        store = VectorStore()
        entries = [_make_entry(id=f"e{i}") for i in range(5)]
        store.upsert_batch(entries)
        self.assertEqual(store.count(), 5)
        store.close()

    def test_upsert_overwrites_existing(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", content="old"))
        store.upsert(_make_entry(id="e1", content="new"))
        self.assertEqual(store.count(), 1)
        results = store.get_by_file("a.py")
        self.assertEqual(results[0].content, "new")
        store.close()


class TestSearch(unittest.TestCase):
    def test_search_returns_sorted_by_similarity(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", embedding=[1.0, 0.0, 0.0]))
        store.upsert(_make_entry(id="e2", embedding=[0.0, 1.0, 0.0]))
        store.upsert(_make_entry(id="e3", embedding=[0.9, 0.1, 0.0]))

        results = store.search([1.0, 0.0, 0.0], top_k=3)
        self.assertEqual(len(results), 3)
        # First result should be the identical vector
        self.assertEqual(results[0][0].id, "e1")
        # Scores should be descending
        self.assertGreaterEqual(results[0][1], results[1][1])
        store.close()

    def test_search_top_k_limit(self) -> None:
        store = VectorStore()
        for i in range(10):
            store.upsert(_make_entry(id=f"e{i}", embedding=[float(i), 0.0, 0.0]))
        results = store.search([9.0, 0.0, 0.0], top_k=3)
        self.assertEqual(len(results), 3)
        store.close()

    def test_search_empty_store(self) -> None:
        store = VectorStore()
        results = store.search([1.0, 0.0, 0.0])
        self.assertEqual(results, [])
        store.close()

    def test_cosine_similarity_identical_vectors(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", embedding=[0.6, 0.8, 0.0]))
        results = store.search([0.6, 0.8, 0.0], top_k=1)
        self.assertAlmostEqual(results[0][1], 1.0, places=5)
        store.close()

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", embedding=[1.0, 0.0, 0.0]))
        results = store.search([0.0, 1.0, 0.0], top_k=1)
        self.assertAlmostEqual(results[0][1], 0.0, places=5)
        store.close()


class TestDeleteAndGet(unittest.TestCase):
    def test_delete_by_file(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", file_path="a.py"))
        store.upsert(_make_entry(id="e2", file_path="b.py"))
        store.delete_by_file("a.py")
        self.assertEqual(store.count(), 1)
        store.close()

    def test_delete_by_file_returns_count(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", file_path="a.py"))
        store.upsert(_make_entry(id="e2", file_path="a.py"))
        count = store.delete_by_file("a.py")
        self.assertEqual(count, 2)
        store.close()

    def test_get_by_file(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1", file_path="a.py"))
        store.upsert(_make_entry(id="e2", file_path="b.py"))
        results = store.get_by_file("a.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_path, "a.py")
        store.close()

    def test_get_by_file_not_found_returns_empty(self) -> None:
        store = VectorStore()
        results = store.get_by_file("nonexistent.py")
        self.assertEqual(results, [])
        store.close()


class TestClearAndClose(unittest.TestCase):
    def test_clear(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1"))
        store.upsert(_make_entry(id="e2"))
        store.clear()
        self.assertEqual(store.count(), 0)
        store.close()

    def test_namespace_isolation(self) -> None:
        import sqlite3
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store_a = VectorStore(db_path=path, namespace="ns_a")
            store_b = VectorStore(db_path=path, namespace="ns_b")

            store_a.upsert(_make_entry(id="e1"))
            store_b.upsert(_make_entry(id="e2"))

            self.assertEqual(store_a.count(), 1)
            self.assertEqual(store_b.count(), 1)

            store_a.clear()
            self.assertEqual(store_a.count(), 0)
            self.assertEqual(store_b.count(), 1)

            store_a.close()
            store_b.close()
        finally:
            os.unlink(path)

    def test_close(self) -> None:
        store = VectorStore()
        store.upsert(_make_entry(id="e1"))
        store.close()
        # After close, operations should raise
        with self.assertRaises(Exception):
            store.count()


if __name__ == "__main__":
    unittest.main()
