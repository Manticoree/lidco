"""Tests for KnowledgeTrigger (T559)."""
from __future__ import annotations
import pytest
from lidco.memory.knowledge_trigger import KnowledgeTrigger, KnowledgeItem, TriggerMatch


def make_kt(tmp_path=None):
    store = str(tmp_path / "knowledge") if tmp_path else None
    return KnowledgeTrigger(store_path=store)


def test_add_and_match(tmp_path):
    kt = make_kt(tmp_path)
    item = KnowledgeItem(id="auth", title="Auth System", content="Use JWT tokens.", triggers=["auth", "login"])
    kt.add(item)
    matches = kt.match("working on auth login flow")
    assert len(matches) == 1
    assert matches[0].item.id == "auth"


def test_no_match(tmp_path):
    kt = make_kt(tmp_path)
    kt.add(KnowledgeItem(id="db", title="DB", content="Use Postgres.", triggers=["database", "postgres"]))
    matches = kt.match("styling the UI button")
    assert matches == []


def test_relevance_scoring(tmp_path):
    kt = make_kt(tmp_path)
    kt.add(KnowledgeItem(id="x", title="X", content="c", triggers=["foo", "bar", "baz"]))
    matches = kt.match("foo bar baz")
    assert matches[0].relevance == 1.0


def test_build_injection(tmp_path):
    kt = make_kt(tmp_path)
    kt.add(KnowledgeItem(id="k1", title="Key Thing", content="Important detail.", triggers=["key"]))
    ctx = kt.build_injection("working on key feature")
    assert not ctx.is_empty()
    assert "Key Thing" in ctx.injected_text


def test_build_injection_empty(tmp_path):
    kt = make_kt(tmp_path)
    ctx = kt.build_injection("random text with no triggers")
    assert ctx.is_empty()
    assert ctx.injected_text == ""


def test_save_and_load(tmp_path):
    store = tmp_path / "knowledge"
    kt1 = KnowledgeTrigger(store_path=str(store))
    kt1.add(KnowledgeItem(id="a", title="A", content="c", triggers=["alpha"]))
    kt1.save()
    kt2 = KnowledgeTrigger(store_path=str(store))
    assert len(kt2.list_items()) == 1


def test_remove(tmp_path):
    kt = make_kt(tmp_path)
    kt.add(KnowledgeItem(id="rem", title="R", content="c", triggers=["r"]))
    removed = kt.remove("rem")
    assert removed is True
    assert len(kt.list_items()) == 0


def test_priority_order(tmp_path):
    kt = make_kt(tmp_path)
    kt.add(KnowledgeItem(id="low", title="Low", content="c", triggers=["x"], priority=0))
    kt.add(KnowledgeItem(id="high", title="High", content="c", triggers=["x"], priority=10))
    matches = kt.match("x")
    assert matches[0].item.id == "high"
