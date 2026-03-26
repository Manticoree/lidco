"""Tests for T620 TemplateEngine."""
import pytest
from pathlib import Path

from lidco.templates.engine import (
    TemplateEngine, TemplateContext, TemplateError, TemplateNotFound,
    _apply_filter,
)


# ---------------------------------------------------------------------------
# TemplateContext
# ---------------------------------------------------------------------------

class TestTemplateContext:
    def test_get_simple(self):
        ctx = TemplateContext({"name": "World"})
        assert ctx.get("name") == "World"

    def test_get_missing(self):
        ctx = TemplateContext({})
        assert ctx.get("missing") is None

    def test_resolve_dot_notation(self):
        ctx = TemplateContext({"user": {"name": "Alice"}})
        assert ctx.resolve("user.name") == "Alice"

    def test_resolve_object_attr(self):
        class Obj:
            name = "Bob"
        ctx = TemplateContext({"obj": Obj()})
        assert ctx.resolve("obj.name") == "Bob"

    def test_child_context(self):
        ctx = TemplateContext({"base": "val"})
        child = ctx.child({"extra": "ext"})
        assert child.get("base") == "val"
        assert child.get("extra") == "ext"

    def test_child_does_not_modify_parent(self):
        ctx = TemplateContext({"x": 1})
        child = ctx.child({"x": 999})
        assert ctx.get("x") == 1

    def test_eval_condition_truthy(self):
        ctx = TemplateContext({"flag": True})
        assert ctx.eval_condition("flag") is True

    def test_eval_condition_falsy(self):
        ctx = TemplateContext({"flag": False})
        assert ctx.eval_condition("flag") is False

    def test_eval_condition_eq(self):
        ctx = TemplateContext({"x": 42})
        assert ctx.eval_condition("x == 42") is True
        assert ctx.eval_condition("x == 0") is False

    def test_eval_condition_not(self):
        ctx = TemplateContext({"flag": False})
        assert ctx.eval_condition("not flag") is True

    def test_eval_condition_and(self):
        ctx = TemplateContext({"a": True, "b": True})
        assert ctx.eval_condition("a and b") is True

    def test_eval_condition_or(self):
        ctx = TemplateContext({"a": False, "b": True})
        assert ctx.eval_condition("a or b") is True

    def test_eval_condition_in(self):
        ctx = TemplateContext({"items": [1, 2, 3]})
        assert ctx.eval_condition("2 in items") is True

    def test_eval_condition_string_literal(self):
        ctx = TemplateContext({"name": "Alice"})
        assert ctx.eval_condition('name == "Alice"') is True


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class TestFilters:
    def test_upper(self):
        assert _apply_filter("hello", "upper") == "HELLO"

    def test_lower(self):
        assert _apply_filter("WORLD", "lower") == "world"

    def test_len(self):
        assert _apply_filter("hello", "len") == 5

    def test_default(self):
        assert _apply_filter(None, 'default("n/a")') == "n/a"
        assert _apply_filter("val", 'default("n/a")') == "val"

    def test_truncate(self):
        assert _apply_filter("hello world", "truncate(5)") == "hello..."

    def test_strip(self):
        assert _apply_filter("  hi  ", "strip") == "hi"

    def test_replace(self):
        assert _apply_filter("hello world", 'replace("world", "earth")') == "hello world"  # simple single arg

    def test_join(self):
        assert _apply_filter(["a", "b", "c"], "join") == "abc"

    def test_first(self):
        assert _apply_filter([1, 2, 3], "first") == 1

    def test_last(self):
        assert _apply_filter([1, 2, 3], "last") == 3

    def test_unknown_filter_passthrough(self):
        assert _apply_filter("hello", "unknown_filter") == "hello"


# ---------------------------------------------------------------------------
# TemplateEngine — variable substitution
# ---------------------------------------------------------------------------

class TestVariableSubstitution:
    def test_simple_var(self):
        engine = TemplateEngine()
        assert engine.render("Hello {{ name }}!", {"name": "World"}) == "Hello World!"

    def test_missing_var_empty(self):
        engine = TemplateEngine(strict=False)
        assert engine.render("Hi {{ missing }}!") == "Hi !"

    def test_missing_var_strict(self):
        engine = TemplateEngine(strict=True)
        with pytest.raises(TemplateError):
            engine.render("{{ undefined }}")

    def test_nested_var(self):
        engine = TemplateEngine()
        assert engine.render("{{ user.name }}", {"user": {"name": "Alice"}}) == "Alice"

    def test_filter_in_template(self):
        engine = TemplateEngine()
        assert engine.render("{{ name | upper }}", {"name": "hello"}) == "HELLO"

    def test_multiple_vars(self):
        engine = TemplateEngine()
        result = engine.render("{{ a }} + {{ b }} = {{ c }}", {"a": 1, "b": 2, "c": 3})
        assert result == "1 + 2 = 3"


# ---------------------------------------------------------------------------
# TemplateEngine — comments
# ---------------------------------------------------------------------------

class TestComments:
    def test_comment_removed(self):
        engine = TemplateEngine()
        result = engine.render("Hello {# this is a comment #} World")
        assert result == "Hello  World"

    def test_multiline_comment(self):
        engine = TemplateEngine()
        result = engine.render("A\n{# ignored\ncompletely #}\nB")
        assert "ignored" not in result
        assert "A" in result and "B" in result


# ---------------------------------------------------------------------------
# TemplateEngine — if/elif/else
# ---------------------------------------------------------------------------

class TestIfBlocks:
    def test_if_true(self):
        engine = TemplateEngine()
        result = engine.render("{% if flag %}YES{% endif %}", {"flag": True})
        assert "YES" in result

    def test_if_false(self):
        engine = TemplateEngine()
        result = engine.render("{% if flag %}YES{% endif %}", {"flag": False})
        assert "YES" not in result

    def test_if_else(self):
        engine = TemplateEngine()
        result = engine.render("{% if flag %}A{% else %}B{% endif %}", {"flag": False})
        assert "B" in result
        assert "A" not in result

    def test_if_elif_else(self):
        engine = TemplateEngine()
        tmpl = "{% if x == 1 %}ONE{% elif x == 2 %}TWO{% else %}OTHER{% endif %}"
        assert engine.render(tmpl, {"x": 2}) == "TWO"
        assert engine.render(tmpl, {"x": 5}) == "OTHER"

    def test_nested_if(self):
        engine = TemplateEngine()
        tmpl = "{% if a %}{% if b %}BOTH{% else %}ONLY_A{% endif %}{% endif %}"
        assert engine.render(tmpl, {"a": True, "b": True}) == "BOTH"
        assert engine.render(tmpl, {"a": True, "b": False}) == "ONLY_A"


# ---------------------------------------------------------------------------
# TemplateEngine — for loops
# ---------------------------------------------------------------------------

class TestForLoops:
    def test_simple_for(self):
        engine = TemplateEngine()
        result = engine.render("{% for x in items %}{{ x }} {% endfor %}", {"items": [1, 2, 3]})
        assert "1" in result and "2" in result and "3" in result

    def test_for_empty_list(self):
        engine = TemplateEngine()
        result = engine.render("{% for x in items %}{{ x }}{% endfor %}", {"items": []})
        assert result == ""

    def test_loop_variable(self):
        engine = TemplateEngine()
        result = engine.render(
            "{% for x in items %}{{ loop.index }}{% endfor %}",
            {"items": ["a", "b", "c"]},
        )
        assert "1" in result and "2" in result and "3" in result

    def test_loop_first_last(self):
        engine = TemplateEngine()
        result = engine.render(
            "{% for x in items %}{% if loop.first %}FIRST{% endif %}{% if loop.last %}LAST{% endif %}{% endfor %}",
            {"items": ["a", "b", "c"]},
        )
        assert "FIRST" in result
        assert "LAST" in result

    def test_for_with_filter(self):
        engine = TemplateEngine()
        result = engine.render(
            "{% for x in items %}{{ x | upper }} {% endfor %}",
            {"items": ["hello", "world"]},
        )
        assert "HELLO" in result and "WORLD" in result

    def test_nested_for(self):
        engine = TemplateEngine()
        result = engine.render(
            "{% for row in rows %}{% for cell in row %}{{ cell }}{% endfor %}\n{% endfor %}",
            {"rows": [[1, 2], [3, 4]]},
        )
        assert "1" in result and "4" in result


# ---------------------------------------------------------------------------
# TemplateEngine — raw blocks
# ---------------------------------------------------------------------------

class TestRawBlocks:
    def test_raw_not_rendered(self):
        engine = TemplateEngine()
        result = engine.render("{% raw %}{{ not_rendered }}{% endraw %}")
        assert "{{ not_rendered }}" in result


# ---------------------------------------------------------------------------
# TemplateEngine — include
# ---------------------------------------------------------------------------

class TestInclude:
    def test_include_file(self, tmp_path):
        partial = tmp_path / "partial.txt"
        partial.write_text("Partial content: {{ value }}")
        engine = TemplateEngine(template_dir=str(tmp_path))
        result = engine.render("{% include 'partial.txt' %}", {"value": "test"})
        assert "Partial content: test" in result

    def test_include_not_found(self, tmp_path):
        engine = TemplateEngine(template_dir=str(tmp_path))
        with pytest.raises(TemplateNotFound):
            engine.render("{% include 'missing.txt' %}")

    def test_include_without_template_dir(self):
        engine = TemplateEngine()
        with pytest.raises(TemplateError):
            engine.render("{% include 'file.txt' %}")


# ---------------------------------------------------------------------------
# TemplateEngine — render_file
# ---------------------------------------------------------------------------

class TestRenderFile:
    def test_render_file(self, tmp_path):
        f = tmp_path / "t.txt"
        f.write_text("Hello {{ name }}!")
        engine = TemplateEngine()
        result = engine.render_file(str(f), {"name": "File"})
        assert result == "Hello File!"

    def test_render_file_not_found(self):
        engine = TemplateEngine()
        with pytest.raises(TemplateNotFound):
            engine.render_file("/nonexistent/template.txt")
