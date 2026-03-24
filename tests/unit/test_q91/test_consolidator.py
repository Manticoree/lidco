"""Tests for lidco.memory.consolidator — MemoryConsolidator TF-IDF merge + stale removal."""

import time

from lidco.memory.consolidator import ConsolidationReport, MemoryConsolidator


# ---------------------------------------------------------------------------
# Test double
# ---------------------------------------------------------------------------

class SimpleMemoryStore:
    """Duck-typed store compatible with MemoryConsolidator."""

    def __init__(self, entries=None):
        self._data = {e["id"]: e for e in (entries or [])}

    def list_all(self):
        return list(self._data.values())

    def delete(self, eid):
        self._data.pop(eid, None)

    def save(self, entry):
        self._data[entry["id"]] = entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(eid, content, use_count=0, tags=None, created_at=None, priority=1):
    return {
        "id": eid,
        "content": content,
        "use_count": use_count,
        "tags": tags or [],
        "created_at": created_at or time.time(),
        "priority": priority,
    }


# ---------------------------------------------------------------------------
# find_similar_groups
# ---------------------------------------------------------------------------

def test_find_similar_groups_clusters_duplicates():
    c = MemoryConsolidator(similarity_threshold=0.5)
    entries = [
        make_entry("a", "python async await coroutine"),
        make_entry("b", "python async await coroutine task"),
        make_entry("c", "completely different topic about databases"),
    ]
    groups = c.find_similar_groups(entries)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_find_similar_groups_no_similar():
    c = MemoryConsolidator(similarity_threshold=0.9)
    entries = [
        make_entry("a", "python async"),
        make_entry("b", "database schema"),
        make_entry("c", "javascript react"),
    ]
    groups = c.find_similar_groups(entries)
    assert groups == []


def test_find_similar_groups_exempt_high_use():
    """Entries with use_count > 10 are never grouped."""
    c = MemoryConsolidator(similarity_threshold=0.1)
    entries = [
        make_entry("vip", "python async await", use_count=20),
        make_entry("low", "python async await", use_count=0),
    ]
    groups = c.find_similar_groups(entries)
    # "low" alone cannot form a group of size > 1, "vip" exempt
    assert groups == []


def test_find_similar_groups_empty_list():
    c = MemoryConsolidator()
    assert c.find_similar_groups([]) == []


# ---------------------------------------------------------------------------
# merge_group
# ---------------------------------------------------------------------------

def test_merge_group_combines_content():
    c = MemoryConsolidator()
    group = [
        make_entry("a", "line one\nline two"),
        make_entry("b", "line two\nline three"),
    ]
    merged = c.merge_group(group)
    assert "line one" in merged["content"]
    assert "line three" in merged["content"]
    # "line two" appears only once (deduped)
    assert merged["content"].count("line two") == 1


def test_merge_group_unions_tags():
    c = MemoryConsolidator()
    group = [
        make_entry("a", "text", tags=["python", "async"]),
        make_entry("b", "text", tags=["async", "await"]),
    ]
    merged = c.merge_group(group)
    assert set(merged["tags"]) >= {"python", "async", "await"}


def test_merge_group_keeps_earliest_created_at():
    c = MemoryConsolidator()
    t_old = time.time() - 1000
    t_new = time.time()
    group = [
        make_entry("a", "text", created_at=t_new),
        make_entry("b", "text", created_at=t_old),
    ]
    merged = c.merge_group(group)
    assert merged["created_at"] == t_old


def test_merge_group_sums_use_counts():
    c = MemoryConsolidator()
    group = [
        make_entry("a", "text", use_count=3),
        make_entry("b", "text", use_count=7),
    ]
    merged = c.merge_group(group)
    assert merged["use_count"] == 10


def test_merge_group_keeps_max_priority():
    c = MemoryConsolidator()
    group = [
        make_entry("a", "text", priority=2),
        make_entry("b", "text", priority=5),
    ]
    merged = c.merge_group(group)
    assert merged["priority"] == 5


def test_merge_group_id_contains_consolidated():
    c = MemoryConsolidator()
    group = [make_entry("alpha", "x"), make_entry("beta", "y")]
    merged = c.merge_group(group)
    assert "consolidated" in merged["id"]


# ---------------------------------------------------------------------------
# consolidate (full pipeline)
# ---------------------------------------------------------------------------

def test_consolidate_reduces_count():
    c = MemoryConsolidator(similarity_threshold=0.5)
    entries = [
        make_entry("a", "python async await coroutine"),
        make_entry("b", "python async await coroutine task"),
    ]
    store = SimpleMemoryStore(entries)
    report = c.consolidate(store)
    assert report.consolidated_count < report.original_count
    assert report.merged_groups >= 1
    assert isinstance(report, ConsolidationReport)


def test_consolidate_removes_stale():
    c = MemoryConsolidator(staleness_ttl_days=1)
    old_time = time.time() - 200000  # ~2.3 days ago
    entries = [
        make_entry("old1", "stale entry", use_count=0, created_at=old_time),
        make_entry("fresh", "recent entry", use_count=5),
    ]
    store = SimpleMemoryStore(entries)
    report = c.consolidate(store)
    assert report.removed_stale == 1
    remaining = [e["id"] for e in store.list_all()]
    assert "fresh" in remaining
    assert "old1" not in remaining


def test_consolidate_stale_with_use_count_preserved():
    """Old entries with use_count > 0 are NOT removed."""
    c = MemoryConsolidator(staleness_ttl_days=1)
    old_time = time.time() - 200000
    entries = [
        make_entry("old_used", "old but used", use_count=3, created_at=old_time),
    ]
    store = SimpleMemoryStore(entries)
    report = c.consolidate(store)
    assert report.removed_stale == 0
    assert len(store.list_all()) == 1


def test_consolidate_preserves_high_use_count():
    c = MemoryConsolidator(similarity_threshold=0.5)
    entries = [
        make_entry("vip", "python async await", use_count=20),
        make_entry("low", "python async await task", use_count=0),
    ]
    store = SimpleMemoryStore(entries)
    c.consolidate(store)
    remaining = [e["id"] for e in store.list_all()]
    assert "vip" in remaining


def test_consolidate_empty_store():
    c = MemoryConsolidator()
    store = SimpleMemoryStore([])
    report = c.consolidate(store)
    assert report.original_count == 0
    assert report.consolidated_count == 0
    assert report.merged_groups == 0
    assert report.removed_stale == 0


def test_consolidate_report_summary_non_empty():
    c = MemoryConsolidator(similarity_threshold=0.5)
    entries = [
        make_entry("a", "python async await coroutine"),
        make_entry("b", "python async await coroutine task"),
    ]
    store = SimpleMemoryStore(entries)
    report = c.consolidate(store)
    assert len(report.summary) > 0
    assert "Merged" in report.summary


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

def test_dry_run_does_not_modify_store():
    c = MemoryConsolidator(similarity_threshold=0.5)
    entries = [
        make_entry("a", "python async await"),
        make_entry("b", "python async await task"),
    ]
    store = SimpleMemoryStore(entries)
    report = c.dry_run(store)
    # Store unchanged
    assert len(list(store.list_all())) == 2
    assert report.merged_groups >= 1
    assert "[dry-run]" in report.summary


def test_dry_run_counts_stale():
    c = MemoryConsolidator(staleness_ttl_days=1)
    old_time = time.time() - 200000
    entries = [
        make_entry("old", "stale", use_count=0, created_at=old_time),
        make_entry("new", "fresh", use_count=1),
    ]
    store = SimpleMemoryStore(entries)
    report = c.dry_run(store)
    assert report.removed_stale == 1
    # But store still has both
    assert len(store.list_all()) == 2


# ---------------------------------------------------------------------------
# max_group_size
# ---------------------------------------------------------------------------

def test_max_group_size_caps_merge():
    c = MemoryConsolidator(similarity_threshold=0.1, max_group_size=2)
    entries = [make_entry(f"e{i}", "python async await coroutine") for i in range(6)]
    groups = c.find_similar_groups(entries)
    for g in groups:
        assert len(g) <= 2


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def test_tokenize_lowercases():
    c = MemoryConsolidator()
    tf = c._tokenize("Hello WORLD hello")
    assert tf.get("hello") == 2
    assert tf.get("world") == 1


def test_cosine_identical_vectors():
    c = MemoryConsolidator()
    a = {"x": 1, "y": 2}
    result = c._cosine(a, a)
    assert abs(result - 1.0) < 1e-9


def test_cosine_orthogonal_vectors():
    c = MemoryConsolidator()
    a = {"x": 1}
    b = {"y": 1}
    assert c._cosine(a, b) == 0.0


def test_cosine_empty_vector():
    c = MemoryConsolidator()
    assert c._cosine({}, {"x": 1}) == 0.0
    assert c._cosine({"x": 1}, {}) == 0.0


def test_similarity_identical_strings():
    c = MemoryConsolidator()
    s = "python async await"
    assert c._similarity(s, s) > 0.99


def test_similarity_empty_strings():
    c = MemoryConsolidator()
    assert c._similarity("", "") == 0.0
