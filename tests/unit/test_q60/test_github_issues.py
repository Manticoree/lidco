"""Tests for GitHub Issues integration — Task 403."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lidco.integrations.github_issues import Issue, IssueClient, _parse_issue


# ---------------------------------------------------------------------------
# _parse_issue
# ---------------------------------------------------------------------------

def test_parse_issue_basic():
    raw = {
        "number": 42,
        "title": "Fix the bug",
        "state": "OPEN",
        "body": "Details here",
        "labels": [{"name": "bug"}, {"name": "priority:high"}],
        "url": "https://github.com/org/repo/issues/42",
    }
    issue = _parse_issue(raw)
    assert issue.number == 42
    assert issue.title == "Fix the bug"
    assert issue.state == "OPEN"
    assert issue.body == "Details here"
    assert issue.labels == ["bug", "priority:high"]
    assert issue.url == "https://github.com/org/repo/issues/42"


def test_parse_issue_empty_labels():
    raw = {"number": 1, "title": "T", "state": "open", "body": "", "labels": [], "url": ""}
    issue = _parse_issue(raw)
    assert issue.labels == []


def test_parse_issue_string_labels():
    """Labels can be plain strings in some gh CLI versions."""
    raw = {"number": 3, "title": "T", "state": "open", "body": "", "labels": ["wontfix"], "url": ""}
    issue = _parse_issue(raw)
    assert issue.labels == ["wontfix"]


def test_parse_issue_missing_fields():
    issue = _parse_issue({})
    assert issue.number == 0
    assert issue.title == ""
    assert issue.state == ""
    assert issue.body == ""
    assert issue.labels == []


def test_issue_dataclass_frozen():
    issue = Issue(1, "T", "open", "body", [], "http://url")
    with pytest.raises((AttributeError, TypeError)):
        issue.title = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IssueClient.list_issues
# ---------------------------------------------------------------------------

def _make_proc(stdout: str, returncode: int = 0):
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = returncode
    return proc


def test_list_issues_success():
    issues_json = json.dumps([
        {"number": 1, "title": "A", "state": "OPEN", "body": "", "labels": [], "url": ""},
        {"number": 2, "title": "B", "state": "OPEN", "body": "", "labels": [{"name": "bug"}], "url": ""},
    ])
    with patch("subprocess.run", return_value=_make_proc(issues_json)):
        client = IssueClient()
        result = client.list_issues()
    assert len(result) == 2
    assert result[0].number == 1
    assert result[1].labels == ["bug"]


def test_list_issues_with_filters():
    """list_issues passes --label flags when labels provided."""
    issues_json = json.dumps([])
    with patch("subprocess.run", return_value=_make_proc(issues_json)) as mock_run:
        IssueClient().list_issues(state="closed", labels=["bug", "docs"], limit=10)
    cmd = mock_run.call_args[0][0]
    assert "--state" in cmd
    assert "closed" in cmd
    assert "--label" in cmd
    assert "bug" in cmd
    assert "docs" in cmd
    assert "--limit" in cmd
    assert "10" in cmd


def test_list_issues_gh_not_installed():
    proc = MagicMock()
    proc.returncode = 127
    proc.stderr = "gh: command not found"
    with patch("subprocess.run", return_value=proc):
        with pytest.raises(RuntimeError, match="gh CLI not installed"):
            IssueClient().list_issues()


def test_list_issues_gh_error():
    proc = MagicMock()
    proc.returncode = 1
    proc.stderr = "Not authenticated"
    with patch("subprocess.run", return_value=proc):
        with pytest.raises(RuntimeError, match="Not authenticated"):
            IssueClient().list_issues()


# ---------------------------------------------------------------------------
# IssueClient.get_issue
# ---------------------------------------------------------------------------

def test_get_issue_success():
    raw = {"number": 7, "title": "Issue Seven", "state": "open", "body": "Body", "labels": [], "url": "http://x"}
    with patch("subprocess.run", return_value=_make_proc(json.dumps(raw))):
        issue = IssueClient().get_issue(7)
    assert issue.number == 7
    assert issue.title == "Issue Seven"


def test_get_issue_error():
    proc = MagicMock()
    proc.returncode = 1
    proc.stderr = "issue not found"
    with patch("subprocess.run", return_value=proc):
        with pytest.raises(RuntimeError):
            IssueClient().get_issue(9999)


# ---------------------------------------------------------------------------
# IssueClient.create_issue
# ---------------------------------------------------------------------------

def test_create_issue_success():
    raw = {"number": 55, "title": "New Feature", "state": "OPEN", "body": "desc", "labels": [], "url": "http://gh"}
    with patch("subprocess.run", return_value=_make_proc(json.dumps(raw))):
        issue = IssueClient().create_issue(title="New Feature", body="desc")
    assert issue.number == 55
    assert issue.title == "New Feature"


def test_create_issue_with_labels():
    raw = {"number": 10, "title": "T", "state": "OPEN", "body": "", "labels": [{"name": "enhancement"}], "url": ""}
    with patch("subprocess.run", return_value=_make_proc(json.dumps(raw))) as mock_run:
        IssueClient().create_issue("T", labels=["enhancement"])
    cmd = mock_run.call_args[0][0]
    assert "--label" in cmd
    assert "enhancement" in cmd


# ---------------------------------------------------------------------------
# IssueClient.close_issue
# ---------------------------------------------------------------------------

def test_close_issue_success():
    with patch("subprocess.run", return_value=_make_proc("")):
        result = IssueClient().close_issue(42)
    assert result is True


def test_close_issue_error():
    proc = MagicMock()
    proc.returncode = 1
    proc.stderr = "Cannot close"
    with patch("subprocess.run", return_value=proc):
        with pytest.raises(RuntimeError):
            IssueClient().close_issue(1)
