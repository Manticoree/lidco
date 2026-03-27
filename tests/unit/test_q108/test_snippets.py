"""Tests for src/lidco/snippets/store.py."""
import tempfile
from pathlib import Path

import pytest

from lidco.snippets.store import Snippet, SnippetError, SnippetStore


def _store() -> SnippetStore:
    return SnippetStore(base_dir=Path(tempfile.mkdtemp()))


class TestSnippet:
    def test_variables_empty(self):
        s = Snippet(name="a", body="no vars here")
        assert s.variables() == []

    def test_variables_detected(self):
        s = Snippet(name="a", body="import ${MODULE}\n${MODULE}.run()")
        assert "MODULE" in s.variables()

    def test_variables_with_default(self):
        s = Snippet(name="a", body="${NAME:world}")
        assert "NAME" in s.variables()

    def test_expand_with_binding(self):
        s = Snippet(name="a", body="Hello, ${NAME}!")
        assert s.expand({"NAME": "Alice"}) == "Hello, Alice!"

    def test_expand_uses_default(self):
        s = Snippet(name="a", body="Hello, ${NAME:world}!")
        assert s.expand() == "Hello, world!"

    def test_expand_missing_no_default(self):
        s = Snippet(name="a", body="${X}")
        assert s.expand() == ""

    def test_matches_query_name(self):
        s = Snippet(name="logger", body="x", description="setup logging")
        assert s.matches_query("logger") is True

    def test_matches_query_description(self):
        s = Snippet(name="x", body="y", description="setup logging")
        assert s.matches_query("logging") is True

    def test_matches_query_tag(self):
        s = Snippet(name="x", body="y", tags=["python"])
        assert s.matches_query("python") is True

    def test_matches_query_no_match(self):
        s = Snippet(name="x", body="y")
        assert s.matches_query("zzz") is False

    def test_word_count(self):
        s = Snippet(name="a", body="one two three")
        assert s.word_count() == 3


class TestSnippetStore:
    def test_save_and_get(self):
        store = _store()
        store.save(Snippet(name="foo", body="pass"))
        s = store.get("foo")
        assert s is not None
        assert s.body == "pass"

    def test_get_nonexistent(self):
        store = _store()
        assert store.get("ghost") is None

    def test_save_empty_name_raises(self):
        store = _store()
        with pytest.raises(SnippetError):
            store.save(Snippet(name="  ", body="x"))

    def test_delete_existing(self):
        store = _store()
        store.save(Snippet(name="x", body="y"))
        assert store.delete("x") is True
        assert store.get("x") is None

    def test_delete_nonexistent(self):
        store = _store()
        assert store.delete("ghost") is False

    def test_list_all(self):
        store = _store()
        store.save(Snippet(name="b", body="2"))
        store.save(Snippet(name="a", body="1"))
        names = [s.name for s in store.list_all()]
        assert names == ["a", "b"]  # sorted

    def test_list_by_language(self):
        store = _store()
        store.save(Snippet(name="py", body="x", language="python"))
        store.save(Snippet(name="js", body="y", language="javascript"))
        py = store.list_all(language="python")
        assert all(s.language == "python" for s in py)

    def test_len(self):
        store = _store()
        assert len(store) == 0
        store.save(Snippet(name="a", body="x"))
        assert len(store) == 1

    def test_search_by_query(self):
        store = _store()
        store.save(Snippet(name="logger", body="x", description="logging"))
        store.save(Snippet(name="formatter", body="y", description="format code"))
        results = store.search("log")
        assert any(s.name == "logger" for s in results)

    def test_search_no_match(self):
        store = _store()
        store.save(Snippet(name="foo", body="x"))
        assert store.search("zzz") == []

    def test_search_by_tag(self):
        store = _store()
        store.save(Snippet(name="a", body="x", tags=["security"]))
        store.save(Snippet(name="b", body="y", tags=["style"]))
        results = store.search("", tags=["security"])
        assert all("security" in s.tags for s in results)

    def test_find_by_tag(self):
        store = _store()
        store.save(Snippet(name="a", body="x", tags=["logging"]))
        results = store.find_by_tag("logging")
        assert len(results) == 1

    def test_expand_by_name(self):
        store = _store()
        store.save(Snippet(name="greet", body="Hello, ${NAME}!"))
        result = store.expand("greet", {"NAME": "World"})
        assert result == "Hello, World!"

    def test_expand_missing_name_raises(self):
        store = _store()
        with pytest.raises(SnippetError):
            store.expand("ghost")

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = SnippetStore(base_dir=tmpdir)
            store1.save(Snippet(name="persist", body="data"))
            store2 = SnippetStore(base_dir=tmpdir)
            assert store2.get("persist") is not None

    def test_overwrite_snippet(self):
        store = _store()
        store.save(Snippet(name="x", body="v1"))
        store.save(Snippet(name="x", body="v2"))
        assert store.get("x").body == "v2"
