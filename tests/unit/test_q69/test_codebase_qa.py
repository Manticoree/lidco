"""Tests for Task 467: CodebaseQA."""
import pytest
from pathlib import Path
from lidco.wiki.qa import CodebaseQA, QAAnswer


def _write_py(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestQAAnswer:
    def test_fields(self):
        ans = QAAnswer(answer="Yes", sources=["src/foo.py"], confidence=0.9)
        assert ans.answer == "Yes"
        assert ans.sources == ["src/foo.py"]
        assert ans.confidence == 0.9


class TestCodebaseQAOffline:
    def test_ask_returns_qa_answer(self, tmp_path):
        _write_py(tmp_path, "auth.py", "def authenticate(user, pwd): pass\n")
        qa = CodebaseQA()
        result = qa.ask("how does authentication work", tmp_path)
        assert isinstance(result, QAAnswer)

    def test_ask_finds_relevant_file(self, tmp_path):
        _write_py(tmp_path, "session.py", "class Session:\n    def __init__(self): self.token = None\n")
        qa = CodebaseQA()
        result = qa.ask("what is the session class", tmp_path)
        assert any("session" in s.lower() for s in result.sources)

    def test_ask_no_results(self, tmp_path):
        qa = CodebaseQA()
        result = qa.ask("quantum teleportation algorithm", tmp_path)
        assert "No relevant" in result.answer or result.confidence == 0.0

    def test_ask_empty_question_returns_something(self, tmp_path):
        qa = CodebaseQA()
        result = qa.ask("", tmp_path)
        # Empty question → no keywords → no results
        assert isinstance(result, QAAnswer)

    def test_ask_with_llm(self, tmp_path):
        _write_py(tmp_path, "cache.py", "class Cache:\n    def get(self, key): pass\n")

        def fake_llm(messages):
            return "The cache uses a dict for storage."

        qa = CodebaseQA(llm_client=fake_llm)
        result = qa.ask("how does cache work", tmp_path)
        assert "cache" in result.answer.lower()
        assert result.confidence > 0.5

    def test_llm_failure_falls_back(self, tmp_path):
        _write_py(tmp_path, "fallback.py", "def process(): pass\n")

        def bad_llm(messages):
            raise RuntimeError("down")

        qa = CodebaseQA(llm_client=bad_llm)
        result = qa.ask("what does process do", tmp_path)
        assert isinstance(result, QAAnswer)

    def test_sources_capped_at_max(self, tmp_path):
        for i in range(10):
            _write_py(tmp_path, f"mod{i}.py", f"def func_{i}(keyword): pass\n")
        qa = CodebaseQA(max_sources=3)
        result = qa.ask("keyword function", tmp_path)
        assert len(result.sources) <= 3

    def test_keyword_extraction(self):
        qa = CodebaseQA()
        kws = qa._extract_keywords("how does the authentication token work")
        assert "authentication" in kws
        assert "token" in kws
        assert "how" not in kws
        assert "the" not in kws
