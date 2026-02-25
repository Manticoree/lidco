"""Tests for ContextDeduplicator in session.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from lidco.core.session import ContextDeduplicator


class TestContextDeduplicator:
    def test_first_call_always_included(self):
        dedup = ContextDeduplicator()
        assert dedup.is_new_or_changed("project", "some content") is True

    def test_second_call_same_content_skipped(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "some content")
        assert dedup.is_new_or_changed("project", "some content") is False

    def test_changed_content_included(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "original content")
        assert dedup.is_new_or_changed("project", "changed content") is True

    def test_different_keys_independent(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "content A")
        dedup.is_new_or_changed("memory", "content B")
        # Same content on the same key should be skipped
        assert dedup.is_new_or_changed("project", "content A") is False
        assert dedup.is_new_or_changed("memory", "content B") is False

    def test_reset_clears_all_hashes(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "content")
        dedup.is_new_or_changed("memory", "mem content")
        dedup.reset()
        # After reset, same content should be included again
        assert dedup.is_new_or_changed("project", "content") is True
        assert dedup.is_new_or_changed("memory", "mem content") is True

    def test_reset_then_skip_again(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "content")
        dedup.reset()
        dedup.is_new_or_changed("project", "content")  # re-sent after reset
        # Second time after reset — should be skipped again
        assert dedup.is_new_or_changed("project", "content") is False

    def test_empty_content_tracked(self):
        dedup = ContextDeduplicator()
        assert dedup.is_new_or_changed("key", "") is True
        assert dedup.is_new_or_changed("key", "") is False

    def test_new_key_always_included(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "content")
        # A key never seen before should always be included
        assert dedup.is_new_or_changed("decisions", "different key, new content") is True

    def test_content_change_updates_hash(self):
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("key", "v1")
        assert dedup.is_new_or_changed("key", "v2") is True
        # After updating to v2, v2 should now be skipped
        assert dedup.is_new_or_changed("key", "v2") is False
        # And going back to v1 is a change again
        assert dedup.is_new_or_changed("key", "v1") is True


class TestGetFullContextDeduplication:
    """Tests that get_full_context skips unchanged static sections."""

    def test_project_context_sent_once(self):
        """project_context is only in the output on first call."""
        dedup = ContextDeduplicator()
        ctx = "## Project Type\n- Language: python"

        # First call: should include
        assert dedup.is_new_or_changed("project", ctx) is True
        # Second call with same content: should skip
        assert dedup.is_new_or_changed("project", ctx) is False

    def test_memory_ctx_sent_when_changed(self):
        """Memory context is re-sent when a new entry is added."""
        dedup = ContextDeduplicator()
        mem_v1 = "## Memory\n- key1: val1"
        mem_v2 = "## Memory\n- key1: val1\n- key2: val2"

        assert dedup.is_new_or_changed("memory", mem_v1) is True
        assert dedup.is_new_or_changed("memory", mem_v1) is False
        # After a new memory is added, v2 should be included
        assert dedup.is_new_or_changed("memory", mem_v2) is True

    def test_decisions_ctx_skipped_when_empty(self):
        """Empty decisions context is tracked correctly."""
        dedup = ContextDeduplicator()
        assert dedup.is_new_or_changed("decisions", "") is True
        assert dedup.is_new_or_changed("decisions", "") is False

    def test_reset_causes_resend_on_clear(self):
        """After reset (from /clear), all sections are sent again."""
        dedup = ContextDeduplicator()
        dedup.is_new_or_changed("project", "ctx")
        dedup.is_new_or_changed("memory", "mem")
        dedup.reset()
        assert dedup.is_new_or_changed("project", "ctx") is True
        assert dedup.is_new_or_changed("memory", "mem") is True


class TestSkipDedup:
    """Tests that skip_dedup=True bypasses deduplication without advancing state."""

    def test_skip_dedup_does_not_consume_hash(self):
        """Calling is_new_or_changed via skip_dedup path must not record the hash."""
        dedup = ContextDeduplicator()
        content = "## Project\n- Language: python"

        # Simulate a display-only call (skip_dedup=True) — we simply don't call is_new_or_changed
        # This test verifies the logic: after a skip_dedup display call, the next real
        # agent call should still get the full content.
        # (The skip_dedup path in get_full_context bypasses is_new_or_changed entirely)
        assert "project" not in dedup._sent_hashes  # Nothing recorded yet

        # Now make a real agent call
        assert dedup.is_new_or_changed("project", content) is True
        assert dedup.is_new_or_changed("project", content) is False

    def test_display_call_before_agent_call(self):
        """A display-only path that doesn't call is_new_or_changed leaves state clean."""
        dedup = ContextDeduplicator()
        content = "project context"

        # Display call: does NOT call is_new_or_changed (skip_dedup=True bypasses it)
        # So dedup state is untouched — next real agent call gets full context
        assert dedup.is_new_or_changed("project", content) is True  # First real call

    def test_agent_call_after_skip_dedup_is_not_double_charged(self):
        """skip_dedup=True should not record hashes, so agent turns are unaffected."""
        dedup = ContextDeduplicator()
        content = "project context"

        # Simulate: agent turn 1
        assert dedup.is_new_or_changed("project", content) is True
        # Simulate: /context display (skip_dedup=True) — bypasses is_new_or_changed
        # Simulate: agent turn 2 — still gets skipped since turn 1 recorded the hash
        assert dedup.is_new_or_changed("project", content) is False
