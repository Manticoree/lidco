"""Tests for PRReviewAgentV2 (T521)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from lidco.review.pr_reviewer_v2 import (
    PRReviewAgentV2,
    PRReviewResult,
    ReviewComment,
)


def _llm_fn_good(prompt: str) -> str:
    return json.dumps({
        "summary": "Looks good overall with minor issues.",
        "verdict": "request_changes",
        "comments": [
            {
                "path": "src/foo.py",
                "line": 10,
                "severity": "critical",
                "body": "Missing error handling",
                "suggestion": "try:\n    ...\nexcept Exception:\n    pass",
            },
            {
                "path": "src/bar.py",
                "line": 5,
                "severity": "suggestion",
                "body": "Consider a list comprehension",
                "suggestion": "",
            },
        ],
    })


def _llm_fn_plain(prompt: str) -> str:
    return "This is fine."


def _llm_fn_raises(prompt: str) -> str:
    raise RuntimeError("LLM error")


@pytest.fixture
def reviewer():
    return PRReviewAgentV2(llm_fn=_llm_fn_good)


# ---- review (with mocked _fetch_diff) ----

def test_review_returns_result(reviewer):
    with patch.object(reviewer, "_fetch_diff", return_value="diff content"):
        result = reviewer.review("owner/repo", 42)
    assert isinstance(result, PRReviewResult)
    assert result.pr_number == 42


def test_review_parses_comments(reviewer):
    with patch.object(reviewer, "_fetch_diff", return_value="some diff"):
        result = reviewer.review("owner/repo", 1)
    assert len(result.comments) == 2
    assert result.comments[0].severity == "critical"
    assert result.comments[0].path == "src/foo.py"


def test_review_verdict(reviewer):
    with patch.object(reviewer, "_fetch_diff", return_value="diff"):
        result = reviewer.review("owner/repo", 1)
    assert result.verdict == "request_changes"


def test_review_no_diff_returns_comment_verdict():
    r = PRReviewAgentV2(llm_fn=_llm_fn_good)
    with patch.object(r, "_fetch_diff", return_value=""):
        result = r.review("owner/repo", 1)
    assert result.verdict == "comment"


def test_review_no_llm_fn():
    r = PRReviewAgentV2(llm_fn=None)
    with patch.object(r, "_fetch_diff", return_value="diff"):
        result = r.review("owner/repo", 1)
    assert result.verdict == "comment"


def test_review_llm_raises():
    r = PRReviewAgentV2(llm_fn=_llm_fn_raises)
    with patch.object(r, "_fetch_diff", return_value="diff"):
        result = r.review("owner/repo", 1)
    assert "LLM error" in result.summary


def test_review_plain_text_response():
    r = PRReviewAgentV2(llm_fn=_llm_fn_plain)
    with patch.object(r, "_fetch_diff", return_value="diff"):
        result = r.review("owner/repo", 1)
    assert "This is fine" in result.summary
    assert result.comments == []


# ---- format_review ----

def test_format_review_contains_verdict(reviewer):
    result = PRReviewResult(
        pr_number=5,
        summary="ok",
        comments=[],
        verdict="approve",
    )
    fmt = reviewer.format_review(result)
    assert "approve" in fmt.lower()
    assert "#5" in fmt


def test_format_review_contains_comments(reviewer):
    result = PRReviewResult(
        pr_number=3,
        summary="review",
        comments=[
            ReviewComment(
                path="a.py", line=1, severity="warning", body="fix this"
            )
        ],
        verdict="comment",
    )
    fmt = reviewer.format_review(result)
    assert "a.py" in fmt
    assert "fix this" in fmt
    assert "WARNING" in fmt


def test_format_review_shows_suggestion_block(reviewer):
    result = PRReviewResult(
        pr_number=1,
        summary="s",
        comments=[
            ReviewComment(
                path="x.py", line=2, severity="critical",
                body="b", suggestion="return None"
            )
        ],
        verdict="request_changes",
    )
    fmt = reviewer.format_review(result)
    assert "suggestion" in fmt
    assert "return None" in fmt


# ---- post_review ----

def test_post_review_returns_false_on_network_error(reviewer):
    result = PRReviewResult(pr_number=1, summary="s", comments=[], verdict="comment")
    with patch("urllib.request.urlopen", side_effect=Exception("no network")):
        ok = reviewer.post_review("owner/repo", 1, result)
    assert ok is False


def test_post_review_returns_true_on_success(reviewer):
    result = PRReviewResult(pr_number=1, summary="s", comments=[], verdict="approve")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        ok = reviewer.post_review("owner/repo", 1, result)
    assert ok is True
