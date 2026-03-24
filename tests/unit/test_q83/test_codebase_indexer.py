"""Tests for CodebaseIndexer (T542)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.indexer.codebase_indexer import CodebaseIndexer, FileEntry, _extract_entry, _sha256


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_build_basic(tmp_path):
    _write(tmp_path, "a.py", "def foo(): pass\n")
    indexer = CodebaseIndexer(tmp_path)
    report = indexer.build()
    assert report.indexed_files == 1
    assert report.total_files == 1


def test_extract_entry_exports(tmp_path):
    p = _write(tmp_path, "m.py", "class Foo:\n    pass\ndef bar(): pass\n")
    content = p.read_text()
    entry = _extract_entry(p, content)
    assert any("Foo" in e for e in entry.exports)
    assert any("bar" in e for e in entry.exports)


def test_extract_entry_imports(tmp_path):
    p = _write(tmp_path, "m.py", "import os\nfrom pathlib import Path\n")
    content = p.read_text()
    entry = _extract_entry(p, content)
    assert "os" in entry.imports


def test_extract_entry_private_skipped(tmp_path):
    p = _write(tmp_path, "m.py", "def _private(): pass\ndef public(): pass\n")
    content = p.read_text()
    entry = _extract_entry(p, content)
    assert not any("_private" in e for e in entry.exports)
    assert any("public" in e for e in entry.exports)


def test_lookup(tmp_path):
    _write(tmp_path, "mod.py", "def my_func(): pass\n")
    indexer = CodebaseIndexer(tmp_path)
    indexer.build()
    results = indexer.lookup("my_func")
    assert len(results) == 1


def test_save_and_load(tmp_path):
    _write(tmp_path, "a.py", "def foo(): pass\n")
    cache = tmp_path / "cache.json"
    indexer = CodebaseIndexer(tmp_path, cache_path=str(cache))
    indexer.build()
    indexer.save()
    indexer2 = CodebaseIndexer(tmp_path, cache_path=str(cache))
    ok = indexer2.load()
    assert ok
    assert len(indexer2.get_index()) == 1


def test_format_summary(tmp_path):
    _write(tmp_path, "pkg/mod.py", "def hello(): pass\n")
    indexer = CodebaseIndexer(tmp_path)
    report = indexer.build()
    summary = report.format_summary()
    assert "files" in summary


def test_sha256_consistent():
    assert _sha256("hello") == _sha256("hello")
    assert _sha256("hello") != _sha256("world")


def test_is_running_false_initially(tmp_path):
    indexer = CodebaseIndexer(tmp_path)
    assert indexer.is_running is False
