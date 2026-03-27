"""Tests for src/lidco/docgen/generator.py."""
import pytest

from lidco.docgen.generator import (
    DocGenError,
    DocGenerator,
    DocStyle,
    FunctionInfo,
    ClassInfo,
    ParamInfo,
)

_SIMPLE_SOURCE = """\
def add(a: int, b: int) -> int:
    return a + b
"""

_CLASS_SOURCE = """\
class Calc:
    def multiply(self, x: float, y: float) -> float:
        return x * y
"""

_WITH_DOCSTRING = """\
def greet(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello, {name}"
"""

_NO_DOCSTRING = """\
def foo():
    pass
"""


class TestParseFunction:
    def test_parse_function_name(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        assert any(f.name == "add" for f in fns)

    def test_parse_params(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        fn = next(f for f in fns if f.name == "add")
        param_names = [p.name for p in fn.params]
        assert "a" in param_names
        assert "b" in param_names

    def test_parse_annotations(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        fn = next(f for f in fns if f.name == "add")
        assert fn.params[0].annotation == "int"

    def test_parse_return_annotation(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        fn = next(f for f in fns if f.name == "add")
        assert fn.return_annotation == "int"

    def test_self_excluded_from_params(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_CLASS_SOURCE)
        method = next(f for f in fns if f.name == "multiply")
        assert all(p.name != "self" for p in method.params)

    def test_has_docstring_true(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_WITH_DOCSTRING)
        assert fns[0].has_docstring() is True

    def test_has_docstring_false(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_NO_DOCSTRING)
        assert fns[0].has_docstring() is False

    def test_syntax_error_raises(self):
        gen = DocGenerator()
        with pytest.raises(DocGenError):
            gen.parse_functions("def (broken")

    def test_async_function(self):
        gen = DocGenerator()
        fns = gen.parse_functions("async def fetch(url: str): pass")
        assert fns[0].is_async is True

    def test_default_param(self):
        gen = DocGenerator()
        fns = gen.parse_functions("def f(x: int = 5): pass")
        assert fns[0].params[0].default == "5"

    def test_has_returns_true(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        assert fns[0].has_returns() is True

    def test_has_returns_none(self):
        gen = DocGenerator()
        fns = gen.parse_functions("def f() -> None: pass")
        assert fns[0].has_returns() is False


class TestParseClass:
    def test_parse_class_name(self):
        gen = DocGenerator()
        classes = gen.parse_classes(_CLASS_SOURCE)
        assert any(c.name == "Calc" for c in classes)

    def test_class_methods(self):
        gen = DocGenerator()
        classes = gen.parse_classes(_CLASS_SOURCE)
        calc = next(c for c in classes if c.name == "Calc")
        assert any(m.name == "multiply" for m in calc.methods)

    def test_class_no_docstring(self):
        gen = DocGenerator()
        classes = gen.parse_classes(_CLASS_SOURCE)
        assert classes[0].has_docstring() is False

    def test_class_with_docstring(self):
        gen = DocGenerator()
        src = 'class Foo:\n    """A foo."""\n    pass\n'
        classes = gen.parse_classes(src)
        assert classes[0].has_docstring() is True


class TestGenerateDocstring:
    def test_google_style_contains_args(self):
        gen = DocGenerator(style=DocStyle.GOOGLE)
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        doc = gen.generate_docstring(fns[0])
        assert "Args:" in doc

    def test_google_style_contains_returns(self):
        gen = DocGenerator(style=DocStyle.GOOGLE)
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        doc = gen.generate_docstring(fns[0])
        assert "Returns:" in doc

    def test_numpy_style_parameters_section(self):
        gen = DocGenerator(style=DocStyle.NUMPY)
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        doc = gen.generate_docstring(fns[0])
        assert "Parameters" in doc

    def test_rst_style_param_tag(self):
        gen = DocGenerator(style=DocStyle.RST)
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        doc = gen.generate_docstring(fns[0])
        assert ":param" in doc

    def test_plain_style(self):
        gen = DocGenerator(style=DocStyle.PLAIN)
        fns = gen.parse_functions(_SIMPLE_SOURCE)
        doc = gen.generate_docstring(fns[0])
        assert "add" in doc

    def test_class_docstring_contains_name(self):
        gen = DocGenerator()
        classes = gen.parse_classes(_CLASS_SOURCE)
        doc = gen.generate_docstring(classes[0])
        assert "Calc" in doc


class TestNeedsDocstring:
    def test_detects_missing(self):
        gen = DocGenerator()
        missing = gen.needs_docstring(_NO_DOCSTRING)
        assert "foo" in missing

    def test_no_missing_when_all_documented(self):
        gen = DocGenerator()
        missing = gen.needs_docstring(_WITH_DOCSTRING)
        assert "greet" not in missing

    def test_class_missing_docstring(self):
        gen = DocGenerator()
        missing = gen.needs_docstring(_CLASS_SOURCE)
        assert "Calc" in missing


class TestInjectDocstring:
    def test_inject_adds_docstring(self):
        gen = DocGenerator()
        fns = gen.parse_functions(_NO_DOCSTRING)
        doc = "Do the thing."
        result = gen.inject_docstring(_NO_DOCSTRING, fns[0], doc)
        assert "Do the thing." in result
        assert '"""' in result
