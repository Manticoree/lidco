"""Tests for Q60/404 — CI/CD pipeline status."""
from __future__ import annotations
import pytest
import json
from unittest.mock import MagicMock, patch
from lidco.integrations.ci_status import CIRun, CIClient, _parse_run


def _sample_raw(**kwargs) -> dict:
    defaults = dict(databaseId=1, name="CI", status="completed", conclusion="success",
                    url="https://github.com/x/y/actions/runs/1", headBranch="main",
                    createdAt="2024-01-01T00:00:00Z", updatedAt="2024-01-01T01:00:00Z")
    defaults.update(kwargs)
    return defaults


class TestCIRun:
    def test_frozen(self):
        run = CIRun(run_id="1", name="CI", status="completed", conclusion="success",
                    url="https://x", branch="main")
        with pytest.raises((AttributeError, TypeError)):
            run.status = "new"  # type: ignore

    def test_fields(self):
        run = CIRun(run_id="1", name="CI", status="in_progress", conclusion="",
                    url="https://x", branch="main")
        assert run.status == "in_progress"
        assert run.conclusion == ""

    def test_branch_field(self):
        run = CIRun(run_id="1", name="CI", status="completed", conclusion="success",
                    url="https://x", branch="feature/x")
        assert run.branch == "feature/x"


class TestParseRun:
    def test_parse_basic(self):
        run = _parse_run(_sample_raw())
        assert run.name == "CI"
        assert run.run_id == "1"

    def test_parse_conclusion(self):
        run = _parse_run(_sample_raw(conclusion="failure"))
        assert run.conclusion == "failure"

    def test_parse_branch(self):
        run = _parse_run(_sample_raw(headBranch="dev"))
        assert run.branch == "dev"

    def test_parse_url(self):
        run = _parse_run(_sample_raw(url="https://example.com/run/42"))
        assert "42" in run.url


class TestCIClient:
    def test_instantiates(self):
        c = CIClient()
        assert c is not None

    def test_gh_not_found(self):
        c = CIClient()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=127, stdout="", stderr="gh: command not found")
            with pytest.raises(RuntimeError, match="gh"):
                c.get_branch_status("main")

    def test_get_branch_status_parses_output(self):
        c = CIClient()
        raw = [_sample_raw()]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw), stderr="")
            with patch("shutil.which", return_value="/usr/bin/gh"):
                runs = c.get_branch_status("main")
        assert len(runs) == 1
        assert runs[0].name == "CI"

    def test_get_current_branch_calls_git(self):
        c = CIClient()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
            branch = c._get_current_branch()
        assert branch == "main"

    def test_gh_error_raises(self):
        c = CIClient()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
            with patch("shutil.which", return_value="/usr/bin/gh"):
                with pytest.raises((RuntimeError, Exception)):
                    c.get_branch_status("main")

    def test_empty_result(self):
        c = CIClient()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            with patch("shutil.which", return_value="/usr/bin/gh"):
                runs = c.get_branch_status("main")
        assert runs == []
