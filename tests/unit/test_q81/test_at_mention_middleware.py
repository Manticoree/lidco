"""Tests for AtMentionMiddleware (T531)."""
import pytest

from lidco.context.at_mention import AtMentionParser, AtMentionProvider
from lidco.context.at_mention_middleware import AtMentionMiddleware, ProcessedInput


def _provider(name, pattern, content="content", tokens=10):
    return AtMentionProvider(
        name=name,
        pattern=pattern,
        fetch_fn=lambda id_: content * (tokens // len(content) + 1),
    )


def _error_provider(name, pattern):
    def _fail(id_):
        raise RuntimeError("fetch failed")
    return AtMentionProvider(name=name, pattern=pattern, fetch_fn=_fail)


@pytest.fixture
def parser():
    p = _provider("gh-issue", r"@gh-issue\s+(\d+)", content="A", tokens=40)
    return AtMentionParser([p])


@pytest.fixture
def middleware(parser):
    return AtMentionMiddleware(parser=parser, max_tokens=4096)


# ---- process ----

def test_process_returns_processed_input(middleware):
    result = middleware.process("Fix @gh-issue 1 today")
    assert isinstance(result, ProcessedInput)


def test_process_clean_text_has_no_mention(middleware):
    result = middleware.process("Fix @gh-issue 1 today")
    assert "@gh-issue" not in result.clean_text


def test_process_injected_context_populated(middleware):
    result = middleware.process("@gh-issue 42")
    assert len(result.injected_context) == 1
    assert result.injected_context[0].provider == "gh-issue"


def test_process_no_mentions(middleware):
    result = middleware.process("plain text message")
    assert result.clean_text == "plain text message"
    assert result.injected_context == []
    assert result.total_tokens == 0


def test_process_total_tokens_sum(middleware):
    result = middleware.process("@gh-issue 1")
    assert result.total_tokens == sum(r.token_estimate for r in result.injected_context)


def test_process_error_in_fetch_recorded():
    ep = _error_provider("gh-issue", r"@gh-issue\s+(\d+)")
    parser = AtMentionParser([ep])
    mw = AtMentionMiddleware(parser=parser, max_tokens=4096)
    result = mw.process("@gh-issue 99")
    assert len(result.errors) == 1
    assert "fetch failed" in result.errors[0]
    assert result.injected_context == []


def test_process_respects_token_budget():
    # Provider returns content with 1000 tokens each
    p = AtMentionProvider(
        name="big",
        pattern=r"@big\s+(\d+)",
        fetch_fn=lambda id_: "A" * 4000,  # 4000//4 = 1000 tokens
    )
    parser = AtMentionParser([p])
    mw = AtMentionMiddleware(parser=parser, max_tokens=1500)
    result = mw.process("@big 1 and @big 2")
    # First fits (1000 ≤ 1500), second doesn't (1000+1000 > 1500)
    assert len(result.injected_context) == 1
    assert result.total_tokens <= 1500


def test_process_parser_exception():
    parser = AtMentionParser()
    # Monkeypatch resolve to raise
    def bad_resolve(text):
        raise RuntimeError("parser exploded")
    parser.resolve = bad_resolve
    mw = AtMentionMiddleware(parser=parser)
    result = mw.process("@something here")
    assert result.clean_text == "@something here"  # original returned
    assert len(result.errors) == 1
