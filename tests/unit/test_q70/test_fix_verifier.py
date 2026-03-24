"""Tests for FixVerifier — T472."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from lidco.review.autofix_agent import FixProposal
from lidco.review.fix_verifier import FixVerifier, VerifyResult


def make_proposal(patch_str="", test_result="ok"):
    return FixProposal(comment_id="c1", patch=patch_str, test_result=test_result, confidence=0.8)


class TestFixVerifier:
    def test_verify_empty_patch_runs_tests(self, tmp_path):
        verifier = FixVerifier(project_dir=tmp_path)
        proposal = make_proposal(patch_str="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5 passed\n", stderr="")
            result = verifier.verify(proposal)
        assert isinstance(result, VerifyResult)

    def test_verify_passed_when_tests_green(self, tmp_path):
        verifier = FixVerifier(project_dir=tmp_path)
        proposal = make_proposal()
        with patch("shutil.copytree"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5 passed", stderr="")
            result = verifier.verify(proposal)
        assert result.passed

    def test_verify_failed_when_tests_red(self, tmp_path):
        verifier = FixVerifier(project_dir=tmp_path)
        proposal = make_proposal()
        with patch("shutil.copytree"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="1 failed", stderr="")
            result = verifier.verify(proposal)
        assert not result.passed

    def test_regression_count_from_output(self, tmp_path):
        verifier = FixVerifier(project_dir=tmp_path)
        proposal = make_proposal()
        with patch("shutil.copytree"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="2 failed, 3 passed", stderr="")
            result = verifier.verify(proposal)
        assert result.regression_count >= 1

    def test_verify_result_dataclass(self):
        r = VerifyResult(passed=True, test_output="ok", regression_count=0)
        assert r.passed
        assert r.regression_count == 0

    def test_copytree_failure_returns_failed(self, tmp_path):
        verifier = FixVerifier(project_dir=tmp_path)
        proposal = make_proposal()
        with patch("shutil.copytree", side_effect=OSError("disk full")):
            result = verifier.verify(proposal)
        assert not result.passed
        assert "disk full" in result.test_output
