"""Tests for SemanticSearch (T568)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.search.semantic_search import SemanticSearch, SearchDocument, _tokenize, _tf, _cosine


def test_tokenize_basic():
    tokens = _tokenize("def my_function(x): pass")
    assert "def" in tokens or "my_function" in tokens


def test_tokenize_produces_list():
    tokens = _tokenize("myFunctionName camelCase")
    assert isinstance(tokens, list)
    assert len(tokens) > 0


def test_tf_sums_to_one():
    tf = _tf(["a", "b", "a"])
    assert abs(sum(tf.values()) - 1.0) < 1e-9


def test_cosine_identical():
    v = {"a": 1.0, "b": 0.5}
    assert abs(_cosine(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal():
    assert _cosine({"a": 1.0}, {"b": 1.0}) == 0.0


def test_add_and_search():
    ss = SemanticSearch()
    ss.add(SearchDocument(id="auth", text="authentication login password user token"))
    ss.add(SearchDocument(id="db", text="database query sql table insert select"))
    results = ss.search("user login authentication")
    assert results[0].doc.id == "auth"


def test_search_empty_corpus():
    ss = SemanticSearch()
    results = ss.search("anything")
    assert results == []


def test_add_file(tmp_path):
    p = tmp_path / "mod.py"
    p.write_text("def authenticate_user(username, password): pass\n")
    ss = SemanticSearch()
    ok = ss.add_file(p)
    assert ok
    assert ss.doc_count == 1


def test_index_directory(tmp_path):
    (tmp_path / "a.py").write_text("import os\n")
    (tmp_path / "b.py").write_text("class Foo: pass\n")
    ss = SemanticSearch()
    count = ss.index_directory(tmp_path)
    assert count == 2


def test_search_code_format(tmp_path):
    (tmp_path / "auth.py").write_text("def login(user, password): pass\n")
    ss = SemanticSearch()
    ss.index_directory(tmp_path)
    result = ss.search_code("user login")
    assert isinstance(result, str) and len(result) > 0
