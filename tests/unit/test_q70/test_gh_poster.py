"""Tests for GHPoster — T473."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from lidco.review.gh_poster import GHPoster, PostResult, ReviewComment


class TestGHPoster:
    def test_post_review_success(self, tmp_path):
        poster = GHPoster(project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=10, body="fix this")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = poster.post_review(42, comments)
        assert result.success
        assert result.posted_count == 1

    def test_deduplication_skips_repeat(self, tmp_path):
        poster = GHPoster(project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=10, body="fix this")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            poster.post_review(42, comments)
            result = poster.post_review(42, comments)  # same comments
        assert result.skipped_count == 1

    def test_clear_cache_resets_dedup(self, tmp_path):
        poster = GHPoster(project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=10, body="fix this")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            poster.post_review(42, comments)
            poster.clear_cache()
            result = poster.post_review(42, comments)
        assert result.posted_count == 1

    def test_post_with_repo(self, tmp_path):
        poster = GHPoster(repo="owner/repo", project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=1, body="b")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            poster.post_review(1, comments)
            call_args = mock_run.call_args[0][0]
        assert "-R" in call_args
        assert "owner/repo" in call_args

    def test_subprocess_failure_skips_comment(self, tmp_path):
        poster = GHPoster(project_dir=tmp_path)
        comments = [ReviewComment(path="a.py", line=1, body="b")]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = poster.post_review(1, comments)
        assert result.skipped_count == 1

    def test_review_comment_hash(self):
        c1 = ReviewComment(path="a.py", line=10, body="fix")
        c2 = ReviewComment(path="a.py", line=10, body="fix")
        assert c1.content_hash() == c2.content_hash()

    def test_different_comments_different_hash(self):
        c1 = ReviewComment(path="a.py", line=10, body="fix")
        c2 = ReviewComment(path="b.py", line=10, body="fix")
        assert c1.content_hash() != c2.content_hash()

    def test_post_result_dataclass(self):
        r = PostResult(success=True, posted_count=3, skipped_count=1)
        assert r.success
        assert r.posted_count == 3
