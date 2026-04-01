"""Tests for KnowledgeShare — team knowledge base with snippets and voting."""

from lidco.collab.knowledge_share import KnowledgeShare, Snippet


class TestAddAndGet:
    def test_add_snippet(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("Title", "Content", "alice")
        assert isinstance(s, Snippet)
        assert s.title == "Title"
        assert s.content == "Content"
        assert s.author == "alice"
        assert s.upvotes == 0

    def test_add_snippet_with_tags(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("T", "C", "a", tags=("python", "testing"))
        assert s.tags == ("python", "testing")

    def test_get_snippet(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("T", "C", "a")
        fetched = ks.get_snippet(s.id)
        assert fetched is not None
        assert fetched.id == s.id

    def test_get_snippet_nonexistent(self):
        ks = KnowledgeShare()
        assert ks.get_snippet("bad_id") is None

    def test_remove_snippet(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("T", "C", "a")
        assert ks.remove_snippet(s.id) is True
        assert ks.get_snippet(s.id) is None

    def test_remove_nonexistent(self):
        ks = KnowledgeShare()
        assert ks.remove_snippet("nope") is False


class TestSearch:
    def test_search_by_title(self):
        ks = KnowledgeShare()
        ks.add_snippet("Python Tricks", "content", "a")
        ks.add_snippet("Java Tips", "content", "a")
        results = ks.search("python")
        assert len(results) == 1
        assert results[0].title == "Python Tricks"

    def test_search_by_content(self):
        ks = KnowledgeShare()
        ks.add_snippet("Title", "Use asyncio.run for tests", "a")
        results = ks.search("asyncio")
        assert len(results) == 1

    def test_search_by_tag(self):
        ks = KnowledgeShare()
        ks.add_snippet("T", "C", "a", tags=("pytest",))
        results = ks.search("pytest")
        assert len(results) == 1

    def test_search_no_results(self):
        ks = KnowledgeShare()
        ks.add_snippet("T", "C", "a")
        assert ks.search("zzzzz") == []


class TestVoting:
    def test_upvote(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("T", "C", "a")
        updated = ks.upvote(s.id)
        assert updated is not None
        assert updated.upvotes == 1

    def test_upvote_multiple(self):
        ks = KnowledgeShare()
        s = ks.add_snippet("T", "C", "a")
        ks.upvote(s.id)
        updated = ks.upvote(s.id)
        assert updated.upvotes == 2

    def test_upvote_nonexistent(self):
        ks = KnowledgeShare()
        assert ks.upvote("nope") is None

    def test_top_snippets(self):
        ks = KnowledgeShare()
        s1 = ks.add_snippet("Low", "C", "a")
        s2 = ks.add_snippet("High", "C", "a")
        ks.upvote(s2.id)
        ks.upvote(s2.id)
        ks.upvote(s1.id)
        top = ks.top_snippets(limit=1)
        assert len(top) == 1
        assert top[0].title == "High"


class TestListByTag:
    def test_list_by_tag(self):
        ks = KnowledgeShare()
        ks.add_snippet("A", "C", "a", tags=("python",))
        ks.add_snippet("B", "C", "a", tags=("rust",))
        assert len(ks.list_by_tag("python")) == 1

    def test_list_by_tag_empty(self):
        ks = KnowledgeShare()
        assert ks.list_by_tag("nope") == []


class TestSuggestAndExport:
    def test_suggest_for_context(self):
        ks = KnowledgeShare()
        ks.add_snippet("Async patterns", "Use asyncio.run", "a", tags=("async",))
        ks.add_snippet("Unrelated", "Nothing", "a")
        results = ks.suggest_for_context("async testing")
        assert any(s.title == "Async patterns" for s in results)

    def test_suggest_ignores_short_words(self):
        ks = KnowledgeShare()
        ks.add_snippet("AB", "ab", "a")
        # Words of length <=2 should be skipped
        results = ks.suggest_for_context("ab")
        assert len(results) == 0

    def test_export_all(self):
        ks = KnowledgeShare()
        ks.add_snippet("T", "C", "alice", tags=("py",))
        exported = ks.export_all()
        assert len(exported) == 1
        assert exported[0]["title"] == "T"
        assert exported[0]["tags"] == ["py"]

    def test_summary(self):
        ks = KnowledgeShare()
        ks.add_snippet("T", "C", "a")
        s = ks.summary()
        assert "Snippets: 1" in s
        assert "Total upvotes: 0" in s
