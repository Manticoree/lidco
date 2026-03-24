"""Tests for RippleAnalyzer (T525)."""
from unittest.mock import MagicMock

import pytest

from lidco.prediction.ripple import RippleAnalyzer, RippleEdit, RippleSuggestion


_DIFF_PYTHON = """\
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,5 +1,5 @@
-def old_function(x):
+def new_function(x, y):
     return x + 1
"""

_DIFF_JS = """\
--- a/src/utils.js
+++ b/src/utils.js
@@ -1,3 +1,3 @@
-function fetchData(url) {
+function fetchData(url, options) {
   return fetch(url);
 }
"""

_DIFF_NO_SYMBOLS = """\
--- a/README.md
+++ b/README.md
@@ -1,2 +1,2 @@
-# Old Title
+# New Title
"""


@pytest.fixture
def analyzer():
    return RippleAnalyzer()


@pytest.fixture
def analyzer_with_graph():
    graph = MagicMock()
    graph.find_references.return_value = [("other.py", 10), ("test.py", 5)]
    return RippleAnalyzer(edit_graph=graph)


# ---- extract_changed_symbols ----

def test_extract_python_function(analyzer):
    symbols = analyzer.extract_changed_symbols(_DIFF_PYTHON)
    assert "old_function" in symbols or "new_function" in symbols


def test_extract_js_function(analyzer):
    symbols = analyzer.extract_changed_symbols(_DIFF_JS)
    assert "fetchData" in symbols


def test_extract_no_symbols(analyzer):
    symbols = analyzer.extract_changed_symbols(_DIFF_NO_SYMBOLS)
    assert symbols == []


def test_extract_deduplicates(analyzer):
    diff = "".join([_DIFF_PYTHON, _DIFF_PYTHON])
    symbols = analyzer.extract_changed_symbols(diff)
    counts = {}
    for s in symbols:
        counts[s] = counts.get(s, 0) + 1
    assert all(c == 1 for c in counts.values())


def test_extract_class_definition(analyzer):
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+class MyClass(Base):\n"
    symbols = analyzer.extract_changed_symbols(diff)
    assert "MyClass" in symbols


# ---- find_references ----

def test_find_references_no_graph(analyzer):
    refs = analyzer.find_references("some_fn")
    assert refs == []


def test_find_references_with_graph(analyzer_with_graph):
    refs = analyzer_with_graph.find_references("fetchData")
    assert len(refs) == 2
    assert refs[0] == ("other.py", 10)


def test_find_references_graph_exception(analyzer):
    graph = MagicMock()
    graph.find_references.side_effect = RuntimeError("boom")
    a = RippleAnalyzer(edit_graph=graph)
    assert a.find_references("x") == []


# ---- suggest_edit ----

def test_suggest_edit_no_llm_fn_returns_stub(analyzer):
    edit = analyzer.suggest_edit("foo.py", 10, "old_fn", "changed signature")
    assert isinstance(edit, RippleEdit)
    assert edit.file == "foo.py"
    assert edit.line == 10
    assert edit.symbol == "old_fn"
    assert "old_fn" in edit.suggested


def test_suggest_edit_with_llm_fn():
    def llm_fn(file, line, symbol, context):
        return f"updated call to {symbol}"

    a = RippleAnalyzer(llm_fn=llm_fn)
    edit = a.suggest_edit("bar.py", 5, "foo", "context")
    assert "foo" in edit.suggested


def test_suggest_edit_llm_fn_exception():
    def bad_fn(file, line, symbol, context):
        raise RuntimeError("llm failed")

    a = RippleAnalyzer(llm_fn=bad_fn)
    edit = a.suggest_edit("x.py", 1, "sym", "ctx")
    assert "[error:" in edit.suggested


# ---- analyze ----

def test_analyze_no_refs_returns_empty(analyzer):
    suggestions = analyzer.analyze(_DIFF_PYTHON)
    assert suggestions == []


def test_analyze_with_graph_returns_suggestions(analyzer_with_graph):
    suggestions = analyzer_with_graph.analyze(_DIFF_PYTHON)
    assert len(suggestions) >= 1
    assert isinstance(suggestions[0], RippleSuggestion)


def test_analyze_ripple_suggestion_has_edits(analyzer_with_graph):
    suggestions = analyzer_with_graph.analyze(_DIFF_PYTHON)
    assert len(suggestions[0].edits) == 2


def test_analyze_source_file_extracted(analyzer_with_graph):
    suggestions = analyzer_with_graph.analyze(_DIFF_PYTHON)
    assert "foo.py" in suggestions[0].source_file
