"""Tests for SessionPinner (T555)."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.context.session_pinning import SessionPinner, PinnedItem


def make_pinner(tmp_path):
    store = tmp_path / "pins.json"
    return SessionPinner(tmp_path, store_path=str(store))


def test_pin_and_get(tmp_path):
    p = make_pinner(tmp_path)
    p.pin("src/mod.py", kind="file")
    pins = p.get_pinned()
    assert len(pins) == 1
    assert pins[0].content == "src/mod.py"


def test_pin_dedup(tmp_path):
    p = make_pinner(tmp_path)
    p.pin("file.py")
    p.pin("file.py")
    pins = p.get_pinned()
    assert len(pins) == 1
    assert pins[0].access_count == 2


def test_unpin(tmp_path):
    p = make_pinner(tmp_path)
    p.pin("x.py")
    removed = p.unpin("x.py")
    assert removed
    assert len(p.get_pinned()) == 0


def test_unpin_not_found(tmp_path):
    p = make_pinner(tmp_path)
    assert p.unpin("nonexistent.py") is False


def test_persist_across_instances(tmp_path):
    store = tmp_path / "pins.json"
    p1 = SessionPinner(tmp_path, store_path=str(store))
    p1.pin("a.py")
    p2 = SessionPinner(tmp_path, store_path=str(store))
    assert len(p2.get_pinned()) == 1


def test_auto_pin_from_session(tmp_path):
    p = make_pinner(tmp_path)
    session = [
        {"content": "editing src/main.py and src/main.py again"},
        {"content": "also look at src/main.py"},
    ]
    count = p.auto_pin_from_session(session)
    assert count >= 1
    names = [pin.content for pin in p.get_pinned()]
    assert any("main.py" in n for n in names)


def test_infer_important_files(tmp_path):
    p = make_pinner(tmp_path)
    session = [
        {"content": "modified config.yaml"},
        {"content": "also config.yaml and config.yaml"},
    ]
    files = p.infer_important_files(session)
    assert any("config.yaml" in f for f in files)


def test_get_report(tmp_path):
    p = make_pinner(tmp_path)
    p.pin("auto.py", source="auto")
    p.pin("manual.py", source="manual")
    report = p.get_report()
    assert report.total_pinned == 2
    assert report.auto_pinned == 1
