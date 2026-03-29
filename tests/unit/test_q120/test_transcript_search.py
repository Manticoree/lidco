"""Tests for src/lidco/memory/transcript_search.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


SAMPLE_TURNS = [
    {"role": "user", "content": "Hello world"},
    {"role": "assistant", "content": "Hi there, how can I help?"},
    {"role": "user", "content": "Tell me about Python programming"},
    {"role": "assistant", "content": "Python is a great language for programming"},
    {"role": "user", "content": "What about JavaScript?"},
    {"role": "assistant", "content": "JavaScript is used for web development"},
    {"role": "user", "content": "Compare Python and JavaScript"},
    {"role": "assistant", "content": "Both Python and JavaScript are popular languages"},
]


class TestSearchMatch:
    def test_fields(self):
        from lidco.memory.transcript_search import SearchMatch
        m = SearchMatch(turn_index=2, snippet="some text", score=3)
        assert m.turn_index == 2
        assert m.snippet == "some text"
        assert m.score == 3


class TestSearchResultSet:
    def test_count_property(self):
        from lidco.memory.transcript_search import SearchResultSet, SearchMatch
        rs = SearchResultSet(query="test", matches=[
            SearchMatch(turn_index=0, snippet="a", score=1),
            SearchMatch(turn_index=1, snippet="b", score=2),
        ])
        assert rs.count == 2

    def test_count_empty(self):
        from lidco.memory.transcript_search import SearchResultSet
        rs = SearchResultSet(query="x", matches=[])
        assert rs.count == 0


class TestTranscriptSearchIndex:
    def test_search_single_word(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("python")
        assert result.count >= 2  # turns 2, 3, 6, 7

    def test_search_empty_query(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("")
        assert result.count == 0

    def test_search_no_match(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("xyznonexistent")
        assert result.count == 0

    def test_search_case_insensitive(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        r1 = idx.search("Python")
        r2 = idx.search("python")
        r3 = idx.search("PYTHON")
        assert r1.count == r2.count == r3.count

    def test_search_multi_word(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("python programming")
        assert result.count >= 1
        # Highest score should be turns with both words
        assert result.matches[0].score >= 2

    def test_search_sorted_by_score_desc(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("python javascript")
        if result.count >= 2:
            for i in range(len(result.matches) - 1):
                assert result.matches[i].score >= result.matches[i + 1].score

    def test_search_query_stored(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("hello")
        assert result.query == "hello"

    def test_snippet_length(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("python")
        for m in result.matches:
            assert len(m.snippet) <= 100

    def test_search_role_content(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("assistant")
        assert result.count >= 1

    def test_update_replaces_index(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        new_turns = [{"role": "user", "content": "totally unique banana"}]
        idx.update(new_turns)
        result = idx.search("banana")
        assert result.count == 1
        result_old = idx.search("python")
        assert result_old.count == 0

    def test_empty_turns(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex([])
        result = idx.search("anything")
        assert result.count == 0

    def test_turn_with_no_content(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        turns = [{"role": "user"}, {"content": "hello"}]
        idx = TranscriptSearchIndex(turns)
        result = idx.search("hello")
        assert result.count >= 1

    def test_special_characters_in_query(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("hello!@#$%")
        assert result.count >= 1  # "hello" still matches

    def test_turn_index_correct(self):
        from lidco.memory.transcript_search import TranscriptSearchIndex
        idx = TranscriptSearchIndex(SAMPLE_TURNS)
        result = idx.search("javascript")
        indices = {m.turn_index for m in result.matches}
        assert 4 in indices or 5 in indices or 6 in indices or 7 in indices


class TestNavigator:
    def test_empty_navigator(self):
        from lidco.memory.transcript_search import Navigator
        nav = Navigator()
        assert nav.has_results() is False
        assert nav.current() is None
        assert nav.position() == (0, 0)

    def test_load_results(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        nav = Navigator()
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=2),
            SearchMatch(turn_index=1, snippet="b", score=1),
        ])
        nav.load(rs)
        assert nav.has_results() is True
        assert nav.current().turn_index == 0

    def test_next(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=3),
            SearchMatch(turn_index=1, snippet="b", score=2),
            SearchMatch(turn_index=2, snippet="c", score=1),
        ])
        nav = Navigator(result_set=rs)
        assert nav.current().turn_index == 0
        n = nav.next()
        assert n.turn_index == 1
        n = nav.next()
        assert n.turn_index == 2

    def test_next_at_end_stays(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=1),
        ])
        nav = Navigator(result_set=rs)
        n = nav.next()
        assert n.turn_index == 0  # stays at last
        n = nav.next()
        assert n.turn_index == 0

    def test_prev(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=3),
            SearchMatch(turn_index=1, snippet="b", score=2),
        ])
        nav = Navigator(result_set=rs)
        nav.next()
        p = nav.prev()
        assert p.turn_index == 0

    def test_prev_at_start_stays(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=1),
        ])
        nav = Navigator(result_set=rs)
        p = nav.prev()
        assert p.turn_index == 0

    def test_position(self):
        from lidco.memory.transcript_search import Navigator, SearchResultSet, SearchMatch
        rs = SearchResultSet(query="x", matches=[
            SearchMatch(turn_index=0, snippet="a", score=3),
            SearchMatch(turn_index=1, snippet="b", score=2),
            SearchMatch(turn_index=2, snippet="c", score=1),
        ])
        nav = Navigator(result_set=rs)
        assert nav.position() == (0, 3)
        nav.next()
        assert nav.position() == (1, 3)

    def test_next_on_empty(self):
        from lidco.memory.transcript_search import Navigator
        nav = Navigator()
        assert nav.next() is None

    def test_prev_on_empty(self):
        from lidco.memory.transcript_search import Navigator
        nav = Navigator()
        assert nav.prev() is None
