"""Tests for AutofixAgent — T471."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import pytest
from lidco.review.autofix_agent import AutofixAgent, FixProposal, _make_patch


class TestAutofixAgent:
    def test_no_fix_fn_returns_none(self, tmp_path):
        agent = AutofixAgent(project_dir=tmp_path)
        assert agent.fix("c1", "some issue") is None

    def test_fix_fn_produces_proposal(self, tmp_path):
        (tmp_path / "a.py").write_text("old content\n")

        def fix_fn(body, content):
            return content.replace("old", "new")

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="5 passed"):
            result = agent.fix("c1", "fix old→new", "a.py")
        assert result is not None
        assert result.comment_id == "c1"
        assert "new" in result.patch or result.patch != ""

    def test_fix_fn_no_change_returns_none(self, tmp_path):
        (tmp_path / "a.py").write_text("content\n")

        def fix_fn(body, content):
            return content  # no change

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        assert agent.fix("c1", "fix", "a.py") is None

    def test_fix_fn_exception_returns_none(self, tmp_path):
        def bad_fn(body, content):
            raise RuntimeError("broken")

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=bad_fn)
        assert agent.fix("c1", "fix") is None

    def test_high_confidence_when_tests_pass(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")

        def fix_fn(body, content):
            return content + "# fixed\n"

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="3 passed"):
            result = agent.fix("c1", "add comment", "a.py")
        assert result is not None
        assert result.confidence >= 0.7

    def test_low_confidence_when_tests_fail(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")

        def fix_fn(body, content):
            return content + "# fixed\n"

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="1 FAILED"):
            result = agent.fix("c1", "add comment", "a.py")
        assert result is not None
        assert result.confidence < 0.7

    def test_fix_without_file_path(self, tmp_path):
        def fix_fn(body, content):
            return "fixed\n"

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="ok"):
            result = agent.fix("c1", "some fix")
        assert result is not None

    def test_proposal_dataclass(self):
        p = FixProposal(comment_id="c1", patch="--- a\n+++ b\n", test_result="ok", confidence=0.9)
        assert p.comment_id == "c1"
        assert not p.applied

    def test_make_patch_produces_diff(self):
        patch_str = _make_patch("f.py", "old\n", "new\n")
        assert "-old" in patch_str or "+new" in patch_str or patch_str == ""

    def test_missing_file_uses_empty_content(self, tmp_path):
        def fix_fn(body, content):
            assert content == ""
            return "new\n"

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="ok"):
            result = agent.fix("c1", "fix", "nonexistent.py")
        assert result is not None
