"""Tests for ReviewIntegration — inline code review."""

from lidco.collab.review_integration import (
    ReviewIntegration,
    ReviewStatus,
    CommentThread,
    ReviewSuggestion,
)


class TestCommentThreads:
    def test_add_comment(self):
        ri = ReviewIntegration()
        t = ri.add_comment("f.py", 10, "alice", "Fix this")
        assert isinstance(t, CommentThread)
        assert t.file_path == "f.py"
        assert t.line == 10
        assert t.author == "alice"
        assert t.body == "Fix this"
        assert t.resolved is False

    def test_get_threads_all(self):
        ri = ReviewIntegration()
        ri.add_comment("a.py", 1, "u", "one")
        ri.add_comment("b.py", 2, "u", "two")
        assert len(ri.get_threads()) == 2

    def test_get_threads_filtered(self):
        ri = ReviewIntegration()
        ri.add_comment("a.py", 1, "u", "one")
        ri.add_comment("b.py", 2, "u", "two")
        assert len(ri.get_threads(file_path="a.py")) == 1

    def test_reply_to_thread(self):
        ri = ReviewIntegration()
        t = ri.add_comment("f.py", 1, "alice", "Issue")
        updated = ri.reply_to(t.id, "bob", "Agreed")
        assert updated is not None
        assert len(updated.replies) == 1
        assert updated.replies[0].author == "bob"

    def test_reply_to_nonexistent(self):
        ri = ReviewIntegration()
        assert ri.reply_to("bad_id", "bob", "text") is None

    def test_resolve_thread(self):
        ri = ReviewIntegration()
        t = ri.add_comment("f.py", 1, "u", "x")
        assert ri.resolve_thread(t.id) is True
        threads = ri.get_threads()
        assert threads[0].resolved is True

    def test_resolve_nonexistent(self):
        ri = ReviewIntegration()
        assert ri.resolve_thread("nope") is False


class TestSuggestions:
    def test_add_suggestion(self):
        ri = ReviewIntegration()
        s = ri.add_suggestion("f.py", 5, "old", "new", "alice")
        assert isinstance(s, ReviewSuggestion)
        assert s.original == "old"
        assert s.replacement == "new"
        assert s.applied is False

    def test_apply_suggestion(self):
        ri = ReviewIntegration()
        s = ri.add_suggestion("f.py", 5, "old", "new", "alice")
        assert ri.apply_suggestion(s.id) is True
        applied = ri.get_suggestions(applied=True)
        assert len(applied) == 1

    def test_apply_nonexistent(self):
        ri = ReviewIntegration()
        assert ri.apply_suggestion("bad") is False

    def test_get_suggestions_unapplied(self):
        ri = ReviewIntegration()
        ri.add_suggestion("f.py", 1, "a", "b", "u")
        s2 = ri.add_suggestion("f.py", 2, "c", "d", "u")
        ri.apply_suggestion(s2.id)
        assert len(ri.get_suggestions(applied=False)) == 1

    def test_get_suggestions_all(self):
        ri = ReviewIntegration()
        ri.add_suggestion("f.py", 1, "a", "b", "u")
        ri.add_suggestion("f.py", 2, "c", "d", "u")
        assert len(ri.get_suggestions()) == 2


class TestReviewStatus:
    def test_initial_status_pending(self):
        ri = ReviewIntegration()
        assert ri._status == ReviewStatus.PENDING

    def test_approve(self):
        ri = ReviewIntegration()
        ri.approve()
        assert ri._status == ReviewStatus.APPROVED

    def test_request_changes(self):
        ri = ReviewIntegration()
        ri.request_changes()
        assert ri._status == ReviewStatus.CHANGES_REQUESTED


class TestSummary:
    def test_summary_content(self):
        ri = ReviewIntegration()
        ri.add_comment("f.py", 1, "u", "x")
        ri.add_suggestion("f.py", 2, "a", "b", "u")
        s = ri.summary()
        assert "pending" in s
        assert "Threads: 1" in s
        assert "Suggestions: 1" in s
