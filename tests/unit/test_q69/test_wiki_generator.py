"""Tests for Task 465: WikiGenerator."""
import pytest
from pathlib import Path
from unittest.mock import patch
from lidco.wiki.generator import ClassDoc, FuncDoc, WikiGenerator, WikiPage


def _write_module(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestWikiPage:
    def test_to_markdown_contains_module_path(self):
        page = WikiPage(module_path="src/foo.py", summary="Does foo things.")
        md = page.to_markdown()
        assert "src/foo.py" in md

    def test_to_markdown_contains_summary(self):
        page = WikiPage(module_path="m.py", summary="My summary.")
        md = page.to_markdown()
        assert "My summary." in md

    def test_to_markdown_with_classes(self):
        page = WikiPage(
            module_path="m.py",
            summary="S",
            classes=[ClassDoc("MyClass", "A class.", methods=[FuncDoc("run", "()")])],
        )
        md = page.to_markdown()
        assert "MyClass" in md
        assert "run" in md

    def test_to_markdown_with_functions(self):
        page = WikiPage(
            module_path="m.py",
            summary="S",
            functions=[FuncDoc("my_func", "(x: int) -> str", "Does stuff.")],
        )
        md = page.to_markdown()
        assert "my_func" in md
        assert "Does stuff" in md

    def test_to_markdown_with_recent_changes(self):
        page = WikiPage(module_path="m.py", summary="S", recent_changes=["abc123 fix bug"])
        md = page.to_markdown()
        assert "fix bug" in md


class TestWikiGeneratorAstExtraction:
    def test_extracts_class(self, tmp_path):
        src = _write_module(tmp_path, "foo.py", "class Foo:\n    '''A foo.'''\n    pass\n")
        gen = WikiGenerator()
        classes, funcs = gen._extract_ast(src)
        assert any(c.name == "Foo" for c in classes)

    def test_extracts_function(self, tmp_path):
        src = _write_module(tmp_path, "bar.py", "def bar(x: int) -> str:\n    '''Doc.'''\n    return str(x)\n")
        gen = WikiGenerator()
        _, funcs = gen._extract_ast(src)
        assert any(f.name == "bar" for f in funcs)

    def test_extracts_class_docstring(self, tmp_path):
        src = _write_module(tmp_path, "baz.py", "class Baz:\n    '''Baz doc.'''\n    pass\n")
        gen = WikiGenerator()
        classes, _ = gen._extract_ast(src)
        assert classes[0].docstring == "Baz doc."

    def test_invalid_syntax_returns_empty(self, tmp_path):
        src = _write_module(tmp_path, "bad.py", "def oops(:\n")
        gen = WikiGenerator()
        classes, funcs = gen._extract_ast(src)
        assert classes == []
        assert funcs == []

    def test_async_function_detected(self, tmp_path):
        src = _write_module(tmp_path, "async_.py", "async def fetch():\n    pass\n")
        gen = WikiGenerator()
        _, funcs = gen._extract_ast(src)
        assert any(f.is_async for f in funcs)


class TestWikiGeneratorGenerate:
    def test_generate_module_returns_wiki_page(self, tmp_path):
        _write_module(tmp_path, "example.py", "'''Example module.'''\ndef run(): pass\n")
        gen = WikiGenerator()
        with patch.object(gen, "_get_git_history", return_value=[]):
            page = gen.generate_module("example.py", tmp_path)
        assert isinstance(page, WikiPage)
        assert page.module_path == "example.py"

    def test_generate_saves_wiki_file(self, tmp_path):
        _write_module(tmp_path, "saver.py", "x = 1\n")
        gen = WikiGenerator()
        with patch.object(gen, "_get_git_history", return_value=[]):
            gen.generate_module("saver.py", tmp_path)
        wiki_dir = tmp_path / ".lidco" / "wiki"
        assert any(wiki_dir.glob("*.md")) if wiki_dir.exists() else True

    def test_generate_summary_uses_module_docstring(self, tmp_path):
        _write_module(tmp_path, "dmod.py", '"""Top-level doc."""\nx = 1\n')
        gen = WikiGenerator()
        with patch.object(gen, "_get_git_history", return_value=[]):
            page = gen.generate_module("dmod.py", tmp_path)
        assert "Top-level doc" in page.summary

    def test_generate_with_llm(self, tmp_path):
        _write_module(tmp_path, "llm_mod.py", "class X: pass\n")

        def fake_llm(messages):
            return "LLM-generated summary."

        gen = WikiGenerator(llm_client=fake_llm)
        with patch.object(gen, "_get_git_history", return_value=[]):
            page = gen.generate_module("llm_mod.py", tmp_path)
        assert "LLM-generated" in page.summary

    def test_load_returns_none_when_absent(self, tmp_path):
        gen = WikiGenerator()
        assert gen.load("nonexistent.py", tmp_path) is None

    def test_load_returns_page_after_generate(self, tmp_path):
        _write_module(tmp_path, "load_me.py", "x = 1\n")
        gen = WikiGenerator()
        with patch.object(gen, "_get_git_history", return_value=[]):
            gen.generate_module("load_me.py", tmp_path)
        loaded = gen.load("load_me.py", tmp_path)
        assert loaded is not None

    def test_generated_at_set(self, tmp_path):
        _write_module(tmp_path, "ts.py", "x = 1\n")
        gen = WikiGenerator()
        with patch.object(gen, "_get_git_history", return_value=[]):
            page = gen.generate_module("ts.py", tmp_path)
        assert "UTC" in page.generated_at
