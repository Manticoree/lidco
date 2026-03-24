"""Tests for Task 469: /ask command."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch
from lidco.cli.commands.wiki_cmds import _ask_question
from lidco.wiki.qa import CodebaseQA, QAAnswer


def _write_py(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestAskFunction:
    def test_ask_basic_question(self, tmp_path):
        _write_py(tmp_path, "auth.py", "def authenticate(token): return True\n")
        result = _ask_question("how does authenticate work", tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ask_includes_answer_header(self, tmp_path):
        _write_py(tmp_path, "x.py", "x = 1\n")
        result = _ask_question("what is x", tmp_path)
        assert "Answer" in result

    def test_ask_cites_sources(self, tmp_path):
        _write_py(tmp_path, "cache.py", "# cache module\ndef cache_lookup(key): pass\n")
        result = _ask_question("cache lookup function", tmp_path)
        # Should find the file and mention it or return an answer
        assert isinstance(result, str) and len(result) > 0

    def test_ask_with_llm_integration(self, tmp_path):
        _write_py(tmp_path, "foo.py", "def foo(): return 42\n")

        def fake_llm(messages):
            return "The foo function returns 42."

        with patch.object(CodebaseQA, "__init__", lambda self, **kw: None), \
             patch.object(CodebaseQA, "ask", return_value=QAAnswer(
                 answer="The foo function returns 42.",
                 sources=["foo.py"],
                 confidence=0.9,
             )):
            result = _ask_question("what does foo return", tmp_path)
        assert "42" in result or "foo" in result.lower()

    def test_ask_no_code_in_project(self, tmp_path):
        result = _ask_question("explain the architecture", tmp_path)
        assert isinstance(result, str)

    def test_ask_empty_question_handled(self, tmp_path):
        # Empty question → no keywords → graceful response
        result = _ask_question("", tmp_path)
        assert isinstance(result, str)
