"""Integration tests for --autofix flow — T475."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from lidco.review.autofix_agent import AutofixAgent, FixProposal
from lidco.review.fix_verifier import FixVerifier, VerifyResult
from lidco.review.gh_poster import GHPoster, ReviewComment, PostResult
from lidco.review.resolution_store import ResolutionStore


class TestAutofixIntegration:
    def test_full_autofix_flow(self, tmp_path):
        """Fix + verify + post pipeline."""
        (tmp_path / "a.py").write_text("x = 1\n")

        def fix_fn(body, content):
            return content + "# fixed\n"

        agent = AutofixAgent(project_dir=tmp_path, fix_fn=fix_fn)
        with patch.object(agent, "_run_tests", return_value="5 passed"):
            proposal = agent.fix("c1", "add comment", "a.py")

        assert proposal is not None

        verifier = FixVerifier(project_dir=tmp_path)
        with patch("shutil.copytree"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5 passed", stderr="")
            verify_result = verifier.verify(proposal)
        assert verify_result.passed

    def test_skip_resolved_comments(self, tmp_path):
        store = ResolutionStore(project_dir=tmp_path)
        store.mark_resolved("use type hints", "a.py", 10)
        assert store.is_resolved("use type hints", "a.py", 10)

    def test_post_after_fix(self, tmp_path):
        poster = GHPoster(project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=10, body="fixed issue", severity="high")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = poster.post_review(1, comments, summary="Auto-fixed 1 issue")
        assert result.success

    def test_autofix_high_severity_only(self, tmp_path):
        """Demonstrate filtering by severity."""
        comments = [
            ReviewComment(path="a.py", line=1, body="critical issue", severity="critical"),
            ReviewComment(path="b.py", line=2, body="info note", severity="info"),
        ]
        high_priority = [c for c in comments if c.severity in ("critical", "high")]
        assert len(high_priority) == 1
        assert high_priority[0].severity == "critical"

    def test_fix_proposal_applied_flag(self):
        p = FixProposal(comment_id="c1", patch="", test_result="ok", confidence=0.9)
        assert not p.applied
        p.applied = True
        assert p.applied

    def test_resolution_persists_across_instances(self, tmp_path):
        store1 = ResolutionStore(project_dir=tmp_path)
        store1.mark_resolved("issue", "f.py", 5)
        store2 = ResolutionStore(project_dir=tmp_path)
        assert store2.is_resolved("issue", "f.py", 5)
