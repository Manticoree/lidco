"""Tests for Q155 bug-fix tasks (887–891)."""
from __future__ import annotations

import threading
import time
import unittest

from lidco.analysis.symbol_index2 import SymbolDef, SymbolIndex, SymbolRef
from lidco.analysis.cross_reference import CrossReference
from lidco.editing.edit_transaction import EditTransaction
from lidco.core.cache import LRUCache, CacheStats
from lidco.logging.structured_logger import LEVEL_ORDER
from lidco.logging.log_router import LogRouter, Route
from lidco.maintenance.disk_usage import DiskUsageAnalyzer, _format_size
from lidco.ui.status_formatter import StatusFormatter


# =====================================================================
# Task 887 — SymbolIndex.list_references() public API
# =====================================================================


class TestSymbolIndexListReferences(unittest.TestCase):
    """Task 887: SymbolIndex.list_references() returns all added refs."""

    def setUp(self) -> None:
        self.idx = SymbolIndex()

    def test_list_references_empty(self) -> None:
        self.assertEqual(self.idx.list_references(), [])

    def test_list_references_returns_all(self) -> None:
        r1 = SymbolRef(name="foo", module="a.py", line=1)
        r2 = SymbolRef(name="bar", module="b.py", line=5)
        self.idx.add_reference(r1)
        self.idx.add_reference(r2)
        refs = self.idx.list_references()
        self.assertEqual(len(refs), 2)
        self.assertIn(r1, refs)
        self.assertIn(r2, refs)

    def test_list_references_returns_copy(self) -> None:
        """Mutating the returned list must not affect the index."""
        self.idx.add_reference(SymbolRef(name="x", module="m.py", line=1))
        refs = self.idx.list_references()
        refs.clear()
        self.assertEqual(len(self.idx.list_references()), 1)


class TestCrossReferenceUsesPublicAPI(unittest.TestCase):
    """Task 887: CrossReference relies on list_references() / list_symbols()."""

    def setUp(self) -> None:
        self.idx = SymbolIndex()
        self.xref = CrossReference(self.idx)

    def test_unused_definitions_all_unused(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_definition(SymbolDef("B", "function", "mod", 5))
        unused = self.xref.unused_definitions()
        names = [d.name for d in unused]
        self.assertIn("A", names)
        self.assertIn("B", names)

    def test_unused_definitions_some_referenced(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_definition(SymbolDef("B", "function", "mod", 5))
        self.idx.add_reference(SymbolRef("A", "other", 10))
        unused = self.xref.unused_definitions()
        names = [d.name for d in unused]
        self.assertNotIn("A", names)
        self.assertIn("B", names)

    def test_undefined_references_none(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_reference(SymbolRef("A", "other", 10))
        self.assertEqual(self.xref.undefined_references(), [])

    def test_undefined_references_some(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_reference(SymbolRef("A", "other", 10))
        self.idx.add_reference(SymbolRef("Z", "other", 11))
        undef = self.xref.undefined_references()
        self.assertEqual(len(undef), 1)
        self.assertEqual(undef[0].name, "Z")

    def test_summary_keys(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_reference(SymbolRef("A", "other", 10))
        s = self.xref.summary()
        self.assertSetEqual(set(s.keys()), {"defined", "referenced", "unused", "undefined"})
        self.assertEqual(s["defined"], 1)
        self.assertEqual(s["referenced"], 1)
        self.assertEqual(s["unused"], 0)
        self.assertEqual(s["undefined"], 0)

    def test_summary_with_mixed(self) -> None:
        self.idx.add_definition(SymbolDef("A", "class", "mod", 1))
        self.idx.add_definition(SymbolDef("B", "function", "mod", 5))
        self.idx.add_reference(SymbolRef("A", "other", 10))
        self.idx.add_reference(SymbolRef("C", "other", 11))
        s = self.xref.summary()
        self.assertEqual(s["defined"], 2)
        self.assertEqual(s["referenced"], 2)
        self.assertEqual(s["unused"], 1)   # B
        self.assertEqual(s["undefined"], 1)  # C


# =====================================================================
# Task 888 — EditTransaction dead-code removal / summary()
# =====================================================================


class TestEditTransactionSummary(unittest.TestCase):
    """Task 888: summary() works correctly after dead code removal."""

    def test_summary_no_changes(self) -> None:
        tx = EditTransaction("empty")
        self.assertEqual(tx.summary(), "no changes")

    def test_summary_single_modify(self) -> None:
        tx = EditTransaction("mod")
        tx.add("a.py", "modify", old_content="old", new_content="new")
        self.assertEqual(tx.summary(), "1 file modified")

    def test_summary_single_create(self) -> None:
        tx = EditTransaction("new")
        tx.add("b.py", "create", new_content="body")
        self.assertEqual(tx.summary(), "1 file created")

    def test_summary_single_delete(self) -> None:
        tx = EditTransaction("del")
        tx.add("c.py", "delete", old_content="body")
        self.assertEqual(tx.summary(), "1 file deleted")

    def test_summary_mixed(self) -> None:
        tx = EditTransaction("mix")
        tx.add("a.py", "modify", old_content="o", new_content="n")
        tx.add("b.py", "modify", old_content="o", new_content="n")
        tx.add("c.py", "create", new_content="n")
        tx.add("d.py", "delete", old_content="o")
        self.assertEqual(tx.summary(), "2 files modified, 1 file created, 1 file deleted")

    def test_summary_plural_creates(self) -> None:
        tx = EditTransaction("many")
        tx.add("a.py", "create", new_content="x")
        tx.add("b.py", "create", new_content="y")
        self.assertEqual(tx.summary(), "2 files created")

    def test_is_empty_flag(self) -> None:
        tx = EditTransaction("t")
        self.assertTrue(tx.is_empty)
        tx.add("a.py", "modify")
        self.assertFalse(tx.is_empty)

    def test_files_affected_deduplication(self) -> None:
        tx = EditTransaction("t")
        tx.add("a.py", "modify", old_content="1", new_content="2")
        tx.add("a.py", "modify", old_content="2", new_content="3")
        tx.add("b.py", "create", new_content="x")
        self.assertEqual(tx.files_affected(), ["a.py", "b.py"])


# =====================================================================
# Task 889 — LRUCache thread safety
# =====================================================================


class TestLRUCacheBasics(unittest.TestCase):
    """Task 889: basic get/put/evict still work."""

    def test_put_get(self) -> None:
        c = LRUCache(maxsize=4)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_get_missing_returns_default(self) -> None:
        c = LRUCache(maxsize=4)
        self.assertIsNone(c.get("nope"))
        self.assertEqual(c.get("nope", 42), 42)

    def test_evict(self) -> None:
        c = LRUCache(maxsize=4)
        c.put("a", 1)
        self.assertTrue(c.evict("a"))
        self.assertFalse(c.evict("a"))
        self.assertIsNone(c.get("a"))

    def test_maxsize_eviction(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)  # should evict "a"
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)

    def test_stats(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", 1)
        c.get("a")        # hit
        c.get("missing")   # miss
        s = c.stats()
        self.assertIsInstance(s, CacheStats)
        self.assertEqual(s.hits, 1)
        self.assertEqual(s.misses, 1)

    def test_lock_attribute_exists(self) -> None:
        c = LRUCache(maxsize=4)
        self.assertTrue(hasattr(c, "_lock"))
        self.assertIsInstance(c._lock, threading.Lock)


class TestLRUCacheConcurrency(unittest.TestCase):
    """Task 889: concurrent access from multiple threads."""

    def test_concurrent_put_get(self) -> None:
        c = LRUCache(maxsize=256)
        errors: list[str] = []

        def writer(start: int) -> None:
            for i in range(start, start + 50):
                c.put(f"k{i}", i)

        def reader(start: int) -> None:
            for i in range(start, start + 50):
                val = c.get(f"k{i}")
                if val is not None and val != i:
                    errors.append(f"k{i}: expected {i} got {val}")

        threads = []
        for batch in range(4):
            threads.append(threading.Thread(target=writer, args=(batch * 50,)))
        for batch in range(4):
            threads.append(threading.Thread(target=reader, args=(batch * 50,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])

    def test_concurrent_evict(self) -> None:
        c = LRUCache(maxsize=128)
        for i in range(100):
            c.put(f"k{i}", i)

        results: list[bool] = []

        def evictor(start: int) -> None:
            for i in range(start, start + 25):
                results.append(c.evict(f"k{i}"))

        threads = [threading.Thread(target=evictor, args=(i * 25,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        # Each key should have been evicted exactly once — 100 True results total
        self.assertEqual(sum(1 for r in results if r), 100)


# =====================================================================
# Task 890 — LEVEL_ORDER deduplication (shared constant)
# =====================================================================


class TestLevelOrderDeduplication(unittest.TestCase):
    """Task 890: LEVEL_ORDER exported from structured_logger, used by log_router."""

    def test_level_order_exported(self) -> None:
        self.assertIsInstance(LEVEL_ORDER, dict)
        self.assertIn("debug", LEVEL_ORDER)
        self.assertIn("info", LEVEL_ORDER)
        self.assertIn("warning", LEVEL_ORDER)
        self.assertIn("error", LEVEL_ORDER)
        self.assertIn("critical", LEVEL_ORDER)

    def test_level_order_ordering(self) -> None:
        self.assertLess(LEVEL_ORDER["debug"], LEVEL_ORDER["info"])
        self.assertLess(LEVEL_ORDER["info"], LEVEL_ORDER["warning"])
        self.assertLess(LEVEL_ORDER["warning"], LEVEL_ORDER["error"])
        self.assertLess(LEVEL_ORDER["error"], LEVEL_ORDER["critical"])

    def test_log_router_uses_shared_constant(self) -> None:
        """LogRouter.route() filters by level using the shared LEVEL_ORDER."""
        router = LogRouter()
        captured: list[str] = []
        router.add_route("sink", handler=lambda rec: captured.append(rec.level), min_level="warning")

        from lidco.logging.structured_logger import LogRecord
        router.route(LogRecord(level="debug", message="lo", timestamp=0, logger_name="t"))
        router.route(LogRecord(level="warning", message="mid", timestamp=0, logger_name="t"))
        router.route(LogRecord(level="error", message="hi", timestamp=0, logger_name="t"))

        # debug should be filtered out
        self.assertEqual(captured, ["warning", "error"])

    def test_log_router_disable_enable(self) -> None:
        router = LogRouter()
        captured: list[str] = []
        router.add_route("s", handler=lambda rec: captured.append(rec.message))
        from lidco.logging.structured_logger import LogRecord
        rec = LogRecord(level="info", message="a", timestamp=0, logger_name="t")
        router.route(rec)
        router.disable("s")
        router.route(rec)
        router.enable("s")
        router.route(rec)
        self.assertEqual(captured, ["a", "a"])  # middle one skipped


# =====================================================================
# Task 891 — format_bytes deduplication
# =====================================================================


class TestFormatBytesDeduplication(unittest.TestCase):
    """Task 891: DiskUsageAnalyzer and StatusFormatter produce same output."""

    def test_bytes_small(self) -> None:
        self.assertEqual(StatusFormatter.format_bytes(0), "0 B")
        self.assertEqual(StatusFormatter.format_bytes(512), "512 B")

    def test_kilobytes(self) -> None:
        result = StatusFormatter.format_bytes(2048)
        self.assertEqual(result, "2.0 KB")

    def test_megabytes(self) -> None:
        result = StatusFormatter.format_bytes(5 * 1024 * 1024)
        self.assertEqual(result, "5.0 MB")

    def test_gigabytes(self) -> None:
        result = StatusFormatter.format_bytes(3 * 1024 * 1024 * 1024)
        self.assertEqual(result, "3.0 GB")

    def test_negative_clamped(self) -> None:
        self.assertEqual(StatusFormatter.format_bytes(-10), "0 B")

    def test_disk_usage_delegates_to_status_formatter(self) -> None:
        """_format_size in disk_usage module delegates to StatusFormatter.format_bytes."""
        test_values = [0, 100, 1024, 1024 * 1024, 1024 * 1024 * 1024]
        for val in test_values:
            self.assertEqual(
                _format_size(val),
                StatusFormatter.format_bytes(val),
                f"Mismatch for {val}",
            )

    def test_disk_usage_format_tree_uses_shared_formatter(self) -> None:
        """DiskUsageAnalyzer.format_tree renders sizes via the shared helper."""
        from unittest.mock import patch
        from lidco.maintenance.disk_usage import UsageEntry

        entries = [
            UsageEntry(path="/proj", size_bytes=2048, file_count=3, is_dir=True),
        ]
        analyzer = DiskUsageAnalyzer()
        tree = analyzer.format_tree(entries)
        # The formatted size should match StatusFormatter output
        self.assertIn(StatusFormatter.format_bytes(2048), tree)


if __name__ == "__main__":
    unittest.main()
