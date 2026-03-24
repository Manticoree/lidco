"""Tests for AtMentionParser (T522)."""
from unittest.mock import patch

import pytest

from lidco.context.at_mention import (
    AtMentionParser,
    AtMentionProvider,
    AtMentionResult,
    make_default_providers,
)


def _provider(name, pattern, response="fetched content"):
    return AtMentionProvider(name=name, pattern=pattern, fetch_fn=lambda id_: response)


def _error_provider(name, pattern):
    def _fail(id_):
        raise RuntimeError("fetch failed")
    return AtMentionProvider(name=name, pattern=pattern, fetch_fn=_fail)


@pytest.fixture
def parser():
    p = _provider("gh-issue", r"@gh-issue\s+(\d+)", "issue body")
    return AtMentionParser([p])


# ---- parse ----

def test_parse_finds_mention(parser):
    results = parser.parse("Fix @gh-issue 42 please")
    assert len(results) == 1
    assert results[0].provider == "gh-issue"
    assert results[0].identifier == "42"
    assert results[0].content == "issue body"


def test_parse_no_mention(parser):
    results = parser.parse("no mentions here")
    assert results == []


def test_parse_multiple_mentions():
    p = _provider("file", r"@file\s+(\S+)", "file content")
    parser = AtMentionParser([p])
    results = parser.parse("check @file foo.py and @file bar.py")
    assert len(results) == 2


def test_parse_error_returns_result_with_error():
    p = _error_provider("file", r"@file\s+(\S+)")
    parser = AtMentionParser([p])
    results = parser.parse("check @file foo.py")
    assert len(results) == 1
    assert results[0].error != ""
    assert results[0].content == ""


def test_parse_token_estimate():
    p = _provider("gh-issue", r"@gh-issue\s+(\d+)", "A" * 40)
    parser = AtMentionParser([p])
    results = parser.parse("@gh-issue 1")
    assert results[0].token_estimate == 10  # 40//4


# ---- resolve ----

def test_resolve_removes_mention(parser):
    clean, results = parser.resolve("Fix @gh-issue 42 please")
    assert "@gh-issue" not in clean
    assert len(results) == 1


def test_resolve_keeps_rest_of_text(parser):
    clean, results = parser.resolve("Please fix @gh-issue 42 today")
    assert "Please fix" in clean
    assert "today" in clean


def test_resolve_no_mentions(parser):
    clean, results = parser.resolve("hello world")
    assert clean == "hello world"
    assert results == []


def test_resolve_multiple_providers():
    p1 = _provider("gh-issue", r"@gh-issue\s+(\d+)", "issue")
    p2 = _provider("file", r"@file\s+(\S+)", "filecontent")
    parser = AtMentionParser([p1, p2])
    clean, results = parser.resolve("see @gh-issue 5 and @file readme.md")
    assert len(results) == 2
    assert "@gh-issue" not in clean
    assert "@file" not in clean


# ---- add_provider ----

def test_add_provider_extends_parser(parser):
    p2 = _provider("url", r"@url\s+(https?://\S+)", "page")
    parser.add_provider(p2)
    results = parser.parse("@url https://example.com")
    assert len(results) == 1
    assert results[0].provider == "url"


# ---- make_default_providers ----

def test_make_default_providers_returns_four():
    providers = make_default_providers()
    assert len(providers) == 4
    names = {p.name for p in providers}
    assert names == {"gh-issue", "url", "file", "shell"}


def test_default_file_provider_reads_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello from file", encoding="utf-8")
    providers = make_default_providers()
    file_prov = next(p for p in providers if p.name == "file")
    content = file_prov.fetch_fn(str(f))
    assert "hello from file" in content


def test_default_file_provider_error():
    providers = make_default_providers()
    file_prov = next(p for p in providers if p.name == "file")
    content = file_prov.fetch_fn("/nonexistent/path/file.txt")
    assert "[file error" in content
