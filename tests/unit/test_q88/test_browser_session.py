"""Tests for BrowserSession (T572)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.browser.browser_session import BrowserSession, BrowserAction, BrowserResult, SessionSummary


def test_session_availability():
    s = BrowserSession()
    assert isinstance(s.is_available, bool)


def test_no_playwright_returns_errors():
    # Patch availability to False
    s = BrowserSession()
    s._available = False
    actions = [BrowserAction(kind="navigate", url="http://example.com")]
    results = asyncio.run(s.run_actions(actions))
    assert len(results) == 1
    assert results[0].success is False
    assert "Playwright" in results[0].error


def test_empty_actions():
    s = BrowserSession()
    s._available = False
    results = asyncio.run(s.run_actions([]))
    assert results == []


def test_summary_empty():
    s = BrowserSession()
    summary = s.summary()
    assert summary.actions_taken == 0
    assert summary.screenshots == 0
    assert summary.errors == 0


def test_history_empty():
    s = BrowserSession()
    assert s.get_history() == []


def test_browser_action_dataclass():
    a = BrowserAction(kind="click", selector="#btn")
    assert a.kind == "click"
    assert a.selector == "#btn"


def test_browser_result_dataclass():
    a = BrowserAction(kind="navigate", url="http://x.com")
    r = BrowserResult(action=a, success=True, output="ok")
    assert r.success is True


def test_session_summary_counts(monkeypatch):
    s = BrowserSession()
    from lidco.browser.browser_session import BrowserAction, BrowserResult
    # Manually populate history
    s._history = [
        BrowserResult(action=BrowserAction(kind="navigate", url="http://x.com"), success=True),
        BrowserResult(action=BrowserAction(kind="screenshot"), success=True),
        BrowserResult(action=BrowserAction(kind="click", selector="#x"), success=False, error="err"),
    ]
    summary = s.summary()
    assert summary.actions_taken == 3
    assert summary.screenshots == 1
    assert summary.errors == 1
    assert summary.final_url == "http://x.com"
