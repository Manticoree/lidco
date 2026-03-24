"""Tests for ContextInspector (T519)."""
from unittest.mock import MagicMock

import pytest

from lidco.context.inspector import ContextInspector, ContextSection, ContextSnapshot


def _make_session(**kwargs):
    s = MagicMock()
    s.system_prompt = kwargs.get("system_prompt", "You are helpful.")
    s.memory_content = kwargs.get("memory_content", "")
    s.rules_content = kwargs.get("rules_content", "")
    s.messages = kwargs.get("messages", [])
    s.tool_results = kwargs.get("tool_results", [])
    s.model_limit = kwargs.get("model_limit", 200_000)
    s.session_id = kwargs.get("session_id", "sess-1")
    return s


# ---- snapshot ----

def test_snapshot_returns_context_snapshot():
    inspector = ContextInspector(_make_session())
    snap = inspector.snapshot()
    assert isinstance(snap, ContextSnapshot)


def test_snapshot_no_session_returns_empty():
    inspector = ContextInspector(None)
    snap = inspector.snapshot()
    assert snap.sections == []
    assert snap.total_tokens == 0


def test_snapshot_includes_system_prompt():
    inspector = ContextInspector(_make_session(system_prompt="Be concise."))
    snap = inspector.snapshot()
    names = [s.name for s in snap.sections]
    assert "system" in names


def test_snapshot_token_estimate():
    inspector = ContextInspector(_make_session(system_prompt="A" * 400))
    snap = inspector.snapshot()
    sys_section = next(s for s in snap.sections if s.name == "system")
    assert sys_section.token_estimate == 100  # 400 // 4


def test_snapshot_total_tokens_sum():
    inspector = ContextInspector(_make_session(
        system_prompt="A" * 40,
        memory_content="B" * 80,
    ))
    snap = inspector.snapshot()
    expected = sum(s.token_estimate for s in snap.sections)
    assert snap.total_tokens == expected


def test_snapshot_model_limit_from_session():
    inspector = ContextInspector(_make_session(model_limit=128_000))
    snap = inspector.snapshot()
    assert snap.model_limit == 128_000


def test_snapshot_session_id():
    inspector = ContextInspector(_make_session(session_id="my-sess"))
    snap = inspector.snapshot()
    assert snap.session_id == "my-sess"


# ---- format_summary ----

def test_format_summary_contains_token_info():
    inspector = ContextInspector(_make_session(system_prompt="hello world"))
    summary = inspector.format_summary()
    assert "tokens" in summary.lower()
    assert "system" in summary


def test_format_summary_empty_session():
    inspector = ContextInspector(None)
    summary = inspector.format_summary()
    assert "0" in summary


# ---- drop ----

def test_drop_removes_section():
    inspector = ContextInspector(_make_session(system_prompt="sys"))
    assert inspector.drop("system") is True
    snap = inspector.snapshot()
    assert all(s.name != "system" for s in snap.sections)


def test_drop_nonexistent_returns_false():
    inspector = ContextInspector(_make_session())
    assert inspector.drop("nonexistent_section") is False


# ---- pin ----

def test_pin_adds_section():
    inspector = ContextInspector(_make_session())
    inspector.pin("important context", label="extra")
    snap = inspector.snapshot()
    names = [s.name for s in snap.sections]
    assert "extra" in names


def test_pinned_sections_returns_list():
    inspector = ContextInspector(_make_session())
    inspector.pin("a", label="x")
    inspector.pin("b", label="y")
    pinned = inspector.pinned_sections()
    assert len(pinned) == 2
    assert {s.name for s in pinned} == {"x", "y"}


def test_pin_is_immutable_list():
    inspector = ContextInspector(_make_session())
    inspector.pin("a")
    p1 = inspector.pinned_sections()
    inspector.pin("b")
    p2 = inspector.pinned_sections()
    assert len(p1) == 1
    assert len(p2) == 2
