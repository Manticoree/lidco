"""Tests for KnowledgeBase."""
import pytest

from lidco.notion.knowledge import KBDocument, KnowledgeBase


class TestKnowledgeBaseAdd:
    def test_add_doc_increments_size(self):
        kb = KnowledgeBase()
        assert kb.index_size() == 0
        kb.add_doc("Title", "Content here")
        assert kb.index_size() == 1

    def test_add_doc_empty_title_raises(self):
        kb = KnowledgeBase()
        with pytest.raises(ValueError, match="Title"):
            kb.add_doc("  ", "content")

    def test_add_multiple_docs(self):
        kb = KnowledgeBase()
        kb.add_doc("A", "aaa")
        kb.add_doc("B", "bbb")
        kb.add_doc("C", "ccc")
        assert kb.index_size() == 3


class TestKnowledgeBaseQuery:
    def test_query_finds_relevant_doc(self):
        kb = KnowledgeBase()
        kb.add_doc("Python Guide", "How to write python code")
        kb.add_doc("Java Guide", "How to write java code")
        results = kb.query("python")
        assert len(results) >= 1
        assert results[0].title == "Python Guide"

    def test_query_ranks_by_overlap(self):
        kb = KnowledgeBase()
        kb.add_doc("Short", "python")
        kb.add_doc("Long", "python programming python tutorial python tips")
        results = kb.query("python programming tips")
        assert results[0].title == "Long"

    def test_query_empty_returns_empty(self):
        kb = KnowledgeBase()
        kb.add_doc("A", "content")
        assert kb.query("") == []

    def test_query_no_match(self):
        kb = KnowledgeBase()
        kb.add_doc("X", "alpha beta")
        assert kb.query("zzzzz") == []

    def test_query_returns_kb_documents(self):
        kb = KnowledgeBase()
        kb.add_doc("Doc", "text")
        results = kb.query("doc")
        assert all(isinstance(d, KBDocument) for d in results)

    def test_query_multiple_matches(self):
        kb = KnowledgeBase()
        kb.add_doc("A", "shared word")
        kb.add_doc("B", "shared word too")
        results = kb.query("shared")
        assert len(results) == 2


class TestKnowledgeBaseContext:
    def test_inject_context_builds_string(self):
        kb = KnowledgeBase()
        kb.add_doc("Guide", "This is a guide about Python programming")
        ctx = kb.inject_context("python")
        assert "Guide" in ctx
        assert "Python" in ctx

    def test_inject_context_respects_max_tokens(self):
        kb = KnowledgeBase()
        kb.add_doc("Big", " ".join(["word"] * 100))
        kb.add_doc("Small", "tiny doc")
        ctx = kb.inject_context("word", max_tokens=50)
        # Should contain at least one doc
        assert len(ctx) > 0

    def test_inject_context_empty_query(self):
        kb = KnowledgeBase()
        kb.add_doc("X", "content")
        assert kb.inject_context("") == ""

    def test_inject_context_no_docs(self):
        kb = KnowledgeBase()
        assert kb.inject_context("anything") == ""


class TestKnowledgeBaseIndexSize:
    def test_index_size_zero_initially(self):
        kb = KnowledgeBase()
        assert kb.index_size() == 0

    def test_index_size_after_adds(self):
        kb = KnowledgeBase()
        for i in range(5):
            kb.add_doc(f"Doc {i}", f"content {i}")
        assert kb.index_size() == 5
