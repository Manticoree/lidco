"""Tests for IssueTrigger — T494."""
from __future__ import annotations
import json
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from lidco.integrations.issue_trigger import Issue, IssueTrigger


def mock_gh_output(issues: list[dict]):
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(issues)
    return result


class TestIssueTrigger:
    def test_poll_returns_new_issues(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        data = [{"number": 1, "title": "Fix bug", "body": "details", "url": "http://x", "labels": []}]
        with patch("subprocess.run", return_value=mock_gh_output(data)):
            issues = trigger.poll()
        assert len(issues) == 1
        assert issues[0].number == 1

    def test_poll_deduplicates(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        data = [{"number": 1, "title": "Bug", "body": "", "url": "", "labels": []}]
        with patch("subprocess.run", return_value=mock_gh_output(data)):
            trigger.poll()  # first poll marks as seen
            new = trigger.poll()  # same issue again
        assert len(new) == 0

    def test_issue_dataclass(self):
        i = Issue(number=42, title="T", body="B", url="U", labels=["bug"])
        assert i.number == 42
        assert i.labels == ["bug"]

    def test_create_branch(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        issue = Issue(number=7, title="T", body="B", url="U")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            branch = trigger.create_branch(issue)
        assert branch == "lidco/issue-7"

    def test_start_stop(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        assert not trigger.is_running
        trigger.start()
        assert trigger.is_running
        trigger.stop()
        assert not trigger.is_running

    def test_gh_failure_returns_empty(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
            issues = trigger.poll()
        assert issues == []

    def test_labels_parsed(self, tmp_path):
        trigger = IssueTrigger(project_dir=tmp_path)
        data = [{"number": 2, "title": "T", "body": "", "url": "", "labels": [{"name": "bug"}, {"name": "p1"}]}]
        with patch("subprocess.run", return_value=mock_gh_output(data)):
            issues = trigger.poll()
        assert "bug" in issues[0].labels
