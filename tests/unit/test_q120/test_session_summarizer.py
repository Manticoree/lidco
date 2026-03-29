"""Tests for src/lidco/memory/session_summarizer.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


SAMPLE_TURNS = [{"role": "user", "content": f"turn {i}"} for i in range(30)]


def fake_summarize(turns):
    return f"Summary of {len(turns)} turns"


class TestSummaryRecord:
    def test_fields(self):
        from lidco.memory.session_summarizer import SummaryRecord
        rec = SummaryRecord(id="s1", summary_text="hello", covered_through_turn=5, created_at="2025-01-01")
        assert rec.id == "s1"
        assert rec.summary_text == "hello"
        assert rec.covered_through_turn == 5
        assert rec.created_at == "2025-01-01"


class TestSessionSummarizerUpdate:
    def test_update_below_threshold_returns_none(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=20)
        result = s.update(SAMPLE_TURNS[:10])
        assert result is None

    def test_update_at_threshold_returns_record(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=20)
        result = s.update(SAMPLE_TURNS[:20])
        assert result is not None
        assert "20" in result.summary_text
        assert result.covered_through_turn == 20

    def test_update_above_threshold(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        result = s.update(SAMPLE_TURNS[:10])
        assert result is not None

    def test_update_force(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=100)
        result = s.update(SAMPLE_TURNS[:5], force=True)
        assert result is not None
        assert "5" in result.summary_text

    def test_update_no_repeat_without_new_turns(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        r1 = s.update(SAMPLE_TURNS[:10])
        assert r1 is not None
        r2 = s.update(SAMPLE_TURNS[:10])  # same turns, no new
        assert r2 is None

    def test_update_with_new_turns(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        r1 = s.update(SAMPLE_TURNS[:10])
        assert r1 is not None
        r2 = s.update(SAMPLE_TURNS[:15])  # more turns
        assert r2 is not None

    def test_update_stores_last_summary(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        last = s.get_last_summary()
        assert last is not None
        assert "10" in last.summary_text

    def test_update_no_summarize_fn(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=None, max_turns_before_summarize=5)
        result = s.update(SAMPLE_TURNS[:10])
        assert result is None

    def test_update_id_is_unique(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        r1 = s.update(SAMPLE_TURNS[:10])
        r2 = s.update(SAMPLE_TURNS[:20])
        assert r1.id != r2.id

    def test_update_created_at_set(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        r = s.update(SAMPLE_TURNS[:10])
        assert r.created_at != ""

    def test_force_with_empty_turns(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        r = s.update([], force=True)
        assert r is not None

    def test_update_summarize_fn_error(self):
        def bad_fn(turns):
            raise RuntimeError("oops")
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=bad_fn, max_turns_before_summarize=5)
        result = s.update(SAMPLE_TURNS[:10])
        assert result is None


class TestSessionSummarizerInjectContext:
    def test_inject_no_summary(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize)
        assert s.inject_context() == ""

    def test_inject_after_update(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        ctx = s.inject_context()
        assert "10" in ctx

    def test_inject_returns_string(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        assert isinstance(s.inject_context(), str)


class TestSessionSummarizerClear:
    def test_clear(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        s.clear()
        assert s.get_last_summary() is None
        assert s.inject_context() == ""

    def test_clear_when_empty(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize)
        s.clear()  # should not raise
        assert s.get_last_summary() is None


class TestSessionSummarizerGetLastSummary:
    def test_get_last_summary_none(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize)
        assert s.get_last_summary() is None

    def test_get_last_summary_after_multiple_updates(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        s.update(SAMPLE_TURNS[:20])
        last = s.get_last_summary()
        assert last is not None
        assert "20" in last.summary_text

    def test_get_last_summary_after_clear_and_update(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize, max_turns_before_summarize=5)
        s.update(SAMPLE_TURNS[:10])
        s.clear()
        s.update(SAMPLE_TURNS[:15])
        last = s.get_last_summary()
        assert "15" in last.summary_text

    def test_default_max_turns(self):
        from lidco.memory.session_summarizer import SessionSummarizer
        s = SessionSummarizer(summarize_fn=fake_summarize)
        # Default is 20
        r = s.update(SAMPLE_TURNS[:19])
        assert r is None
        r = s.update(SAMPLE_TURNS[:20])
        assert r is not None
