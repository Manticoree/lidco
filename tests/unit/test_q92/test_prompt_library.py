"""Tests for src/lidco/prompts/library.py."""

import pytest
from pathlib import Path
from lidco.prompts.library import PromptTemplate, PromptTemplateLibrary, RenderResult


def make_lib(tmp_path: Path) -> PromptTemplateLibrary:
    return PromptTemplateLibrary(project_root=tmp_path)


def write_template(directory: Path, name: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestPromptTemplateDataclass:
    def test_fields(self, tmp_path):
        tpl = PromptTemplate(
            name="test",
            content="Hello",
            variables=[],
            source_path=str(tmp_path / "test.md"),
        )
        assert tpl.name == "test"
        assert tpl.content == "Hello"
        assert tpl.variables == []
        assert "test.md" in tpl.source_path

    def test_variables_populated(self, tmp_path):
        tpl = PromptTemplate(
            name="greet",
            content="Hello {{name}}!",
            variables=["name"],
            source_path="greet.md",
        )
        assert "name" in tpl.variables


class TestRenderResultDataclass:
    def test_defaults(self):
        r = RenderResult(name="foo", rendered="bar")
        assert r.missing_vars == []
        assert r.found is True  # B1: found defaults to True

    def test_not_found_flag(self):
        r = RenderResult(name="x", rendered="", found=False)
        assert r.found is False

    def test_with_missing(self):
        r = RenderResult(name="x", rendered="", missing_vars=["a", "b"])
        assert len(r.missing_vars) == 2


class TestExtractVariables:
    def test_no_vars(self, tmp_path):
        lib = make_lib(tmp_path)
        assert lib._extract_variables("Hello world") == []

    def test_single_var(self, tmp_path):
        lib = make_lib(tmp_path)
        assert lib._extract_variables("Hello {{name}}!") == ["name"]

    def test_multiple_vars(self, tmp_path):
        lib = make_lib(tmp_path)
        assert lib._extract_variables("{{a}} and {{b}} and {{a}}") == ["a", "b"]

    def test_order_preserved(self, tmp_path):
        lib = make_lib(tmp_path)
        result = lib._extract_variables("{{z}} then {{m}} then {{a}}")
        assert result == ["z", "m", "a"]


class TestList:
    def test_empty_dirs(self, tmp_path):
        lib = make_lib(tmp_path)
        assert lib.list() == []

    def test_project_template_found(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "fix-bug", "Fix the {{language}} bug")
        lib = make_lib(tmp_path)
        templates = lib.list()
        assert len(templates) == 1
        assert templates[0].name == "fix-bug"

    def test_sorted_by_name(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "zebra", "Z")
        write_template(proj_dir, "alpha", "A")
        lib = make_lib(tmp_path)
        names = [t.name for t in lib.list()]
        assert names == sorted(names)

    def test_project_overrides_global(self, tmp_path, monkeypatch):
        proj_dir = tmp_path / ".lidco" / "prompts"
        global_dir = tmp_path / "global_home" / ".lidco" / "prompts"
        write_template(proj_dir, "shared", "project version")
        write_template(global_dir, "shared", "global version")
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "global_home")
        lib = make_lib(tmp_path)
        templates = lib.list()
        assert len(templates) == 1
        assert templates[0].content == "project version"


class TestLoad:
    def test_not_found_returns_none(self, tmp_path):
        lib = make_lib(tmp_path)
        assert lib.load("missing") is None

    def test_load_from_project(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "review", "Review {{pr_url}}")
        lib = make_lib(tmp_path)
        tpl = lib.load("review")
        assert tpl is not None
        assert tpl.name == "review"
        assert "pr_url" in tpl.variables

    def test_project_priority_over_global(self, tmp_path, monkeypatch):
        proj_dir = tmp_path / ".lidco" / "prompts"
        global_dir = tmp_path / "home" / ".lidco" / "prompts"
        write_template(proj_dir, "tpl", "project")
        write_template(global_dir, "tpl", "global")
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        lib = make_lib(tmp_path)
        assert lib.load("tpl").content == "project"


class TestRender:
    def test_no_vars(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "plain", "Hello world")
        lib = make_lib(tmp_path)
        result = lib.render("plain")
        assert result.rendered == "Hello world"
        assert result.missing_vars == []
        assert result.found is True

    def test_var_substitution(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "greet", "Hello {{name}}!")
        lib = make_lib(tmp_path)
        result = lib.render("greet", {"name": "Alice"})
        assert result.rendered == "Hello Alice!"
        assert result.missing_vars == []

    def test_var_with_spaces(self, tmp_path):
        # B7: {{ var }} with whitespace should also be substituted
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "spaced", "Hello {{ name }}!")
        lib = make_lib(tmp_path)
        result = lib.render("spaced", {"name": "Bob"})
        assert result.rendered == "Hello Bob!"

    def test_missing_var_reported(self, tmp_path):
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "greet", "Hello {{name}}!")
        lib = make_lib(tmp_path)
        result = lib.render("greet", {})
        assert "name" in result.missing_vars

    def test_template_not_found_sets_found_false(self, tmp_path):
        # B1: found=False distinguishes not-found from empty template
        lib = make_lib(tmp_path)
        result = lib.render("nonexistent")
        assert result.rendered == ""
        assert result.found is False

    def test_empty_template_found_true(self, tmp_path):
        # B1: an empty file should have found=True
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "empty", "")
        lib = make_lib(tmp_path)
        result = lib.render("empty")
        assert result.found is True
        assert result.rendered == ""


class TestLoadPathErrorHandling:
    def test_unreadable_file_skipped_in_list(self, tmp_path):
        # B8: unreadable files should not crash list()
        proj_dir = tmp_path / ".lidco" / "prompts"
        write_template(proj_dir, "good", "good content")
        bad = proj_dir / "bad.md"
        bad.write_bytes(b"\xff\xfe invalid utf8 \x80")  # invalid UTF-8
        lib = make_lib(tmp_path)
        templates = lib.list()
        names = [t.name for t in templates]
        assert "good" in names
        assert "bad" not in names

    def test_unreadable_file_returns_none_in_load(self, tmp_path):
        # B8: load() returns None when file is unreadable
        proj_dir = tmp_path / ".lidco" / "prompts"
        bad = proj_dir / "bad.md"
        proj_dir.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"\xff\xfe \x80")
        lib = make_lib(tmp_path)
        assert lib.load("bad") is None


class TestSave:
    def test_save_creates_file(self, tmp_path):
        lib = make_lib(tmp_path)
        tpl = lib.save("new-tpl", "Content with {{var}}")
        expected = tmp_path / ".lidco" / "prompts" / "new-tpl.md"
        assert expected.exists()
        assert expected.read_text() == "Content with {{var}}"

    def test_save_returns_template(self, tmp_path):
        lib = make_lib(tmp_path)
        tpl = lib.save("check", "{{a}} + {{b}}")
        assert tpl.name == "check"
        assert tpl.variables == ["a", "b"]

    def test_save_then_load(self, tmp_path):
        lib = make_lib(tmp_path)
        lib.save("roundtrip", "Round trip {{x}}")
        loaded = lib.load("roundtrip")
        assert loaded is not None
        assert loaded.content == "Round trip {{x}}"
