"""Tests for SelfReviewer — T491."""
from __future__ import annotations
import pytest
from lidco.review.self_review import SelfReviewResult, SelfReviewer


SAMPLE_DIFF = """--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 def foo():
-    pass
+    return 42
"""


class TestSelfReviewer:
    def test_no_review_fn_returns_default(self):
        reviewer = SelfReviewer()
        result = reviewer.review(SAMPLE_DIFF)
        assert isinstance(result, SelfReviewResult)
        assert result.score >= 0.5

    def test_empty_diff_returns_perfect_score(self):
        reviewer = SelfReviewer()
        result = reviewer.review("")
        assert result.score == 1.0
        assert not result.needs_revision

    def test_review_fn_called(self):
        def review_fn(diff, ctx):
            return {"issues": ["minor style issue"], "score": 0.9, "suggestions": "use f-string"}
        reviewer = SelfReviewer(review_fn=review_fn)
        result = reviewer.review(SAMPLE_DIFF)
        assert result.score == 0.9
        assert result.issues == ["minor style issue"]

    def test_score_below_08_needs_revision(self):
        def review_fn(diff, ctx):
            return {"issues": ["critical bug"], "score": 0.6, "suggestions": "fix the bug"}
        reviewer = SelfReviewer(review_fn=review_fn)
        result = reviewer.review(SAMPLE_DIFF)
        assert result.needs_revision

    def test_score_above_08_no_revision(self):
        def review_fn(diff, ctx):
            return {"issues": [], "score": 0.85, "suggestions": ""}
        reviewer = SelfReviewer(review_fn=review_fn)
        result = reviewer.review(SAMPLE_DIFF)
        assert not result.needs_revision

    def test_review_fn_exception_returns_fallback(self):
        def bad_fn(diff, ctx):
            raise RuntimeError("LLM down")
        reviewer = SelfReviewer(review_fn=bad_fn)
        result = reviewer.review(SAMPLE_DIFF)
        assert isinstance(result, SelfReviewResult)

    def test_review_with_iterations_stops_early(self):
        call_count = {"n": 0}
        def review_fn(diff, ctx):
            call_count["n"] += 1
            return {"issues": [], "score": 0.9, "suggestions": ""}
        reviewer = SelfReviewer(review_fn=review_fn)
        result = reviewer.review_with_iterations(SAMPLE_DIFF)
        assert call_count["n"] == 1  # stopped early, score good

    def test_review_with_iterations_max_2(self):
        call_count = {"n": 0}
        def review_fn(diff, ctx):
            call_count["n"] += 1
            return {"issues": ["bug"], "score": 0.5, "suggestions": "fix"}
        def fix_fn(diff, suggestions):
            return diff + "\n# fixed"
        reviewer = SelfReviewer(review_fn=review_fn)
        reviewer.review_with_iterations(SAMPLE_DIFF, fix_fn=fix_fn)
        assert call_count["n"] <= SelfReviewer.MAX_ITERATIONS

    def test_result_dataclass(self):
        r = SelfReviewResult(issues=[], score=0.9, needs_revision=False, suggestions="")
        assert not r.needs_revision
