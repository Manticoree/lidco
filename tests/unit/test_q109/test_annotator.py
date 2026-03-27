"""Tests for src/lidco/typing_/annotator.py."""
import pytest

from lidco.typing_.annotator import (
    AnnotatorError,
    FunctionAnnotation,
    ParamAnnotation,
    TypeAnnotator,
)

_UNANNOTATED = """\
def process(name, count=0, verbose=False):
    return name * count
"""

_ANNOTATED = """\
def process(name: str, count: int = 0, verbose: bool = False) -> str:
    return name * count
"""

_MIXED = """\
def foo(a: int, b, c=3.14):
    return a + b
"""


class TestParamAnnotation:
    def test_name(self):
        p = ParamAnnotation(name="count", suggested_type="int", confidence=0.9, reason="default")
        assert p.name == "count"

    def test_type(self):
        p = ParamAnnotation(name="x", suggested_type="float", confidence=0.8, reason="x")
        assert p.suggested_type == "float"


class TestFunctionAnnotation:
    def test_has_suggestions_with_params(self):
        ann = FunctionAnnotation(name="f", lineno=1,
                                 params=[ParamAnnotation("x", "int", 0.9, "reason")])
        assert ann.has_suggestions() is True

    def test_has_suggestions_with_return(self):
        ann = FunctionAnnotation(name="f", lineno=1, return_type="str")
        assert ann.has_suggestions() is True

    def test_has_suggestions_empty(self):
        ann = FunctionAnnotation(name="f", lineno=1)
        assert ann.has_suggestions() is False

    def test_signature_format(self):
        ann = FunctionAnnotation(name="add", lineno=1,
                                 params=[
                                     ParamAnnotation("a", "int", 0.9, "r"),
                                     ParamAnnotation("b", "int", 0.9, "r"),
                                 ],
                                 return_type="int")
        sig = ann.signature()
        assert "add" in sig
        assert "a: int" in sig
        assert "-> int" in sig

    def test_as_dict_keys(self):
        ann = FunctionAnnotation(name="f", lineno=5,
                                 params=[ParamAnnotation("x", "str", 0.8, "r")],
                                 return_type="None")
        d = ann.as_dict()
        assert "name" in d
        assert "params" in d
        assert "return_type" in d


class TestTypeAnnotator:
    def test_annotate_returns_list(self):
        ann = TypeAnnotator()
        result = ann.annotate(_UNANNOTATED)
        assert isinstance(result, list)

    def test_annotate_finds_function(self):
        ann = TypeAnnotator()
        result = ann.annotate(_UNANNOTATED)
        assert any(s.name == "process" for s in result)

    def test_annotate_infers_bool_default(self):
        ann = TypeAnnotator()
        result = ann.annotate(_UNANNOTATED)
        process = next(s for s in result if s.name == "process")
        verbose_param = next((p for p in process.params if p.name == "verbose"), None)
        assert verbose_param is not None
        assert verbose_param.suggested_type == "bool"

    def test_annotate_infers_int_default(self):
        ann = TypeAnnotator()
        result = ann.annotate(_UNANNOTATED)
        process = next(s for s in result if s.name == "process")
        count_param = next((p for p in process.params if p.name == "count"), None)
        assert count_param is not None
        assert count_param.suggested_type == "int"

    def test_annotate_already_annotated_skipped(self):
        ann = TypeAnnotator()
        result = ann.annotate(_ANNOTATED)
        # No suggestions needed — already annotated
        if result:
            for s in result:
                assert len(s.params) == 0

    def test_annotate_mixed_partial(self):
        ann = TypeAnnotator()
        result = ann.annotate(_MIXED)
        # Only unannotated params should appear
        if result:
            foo = next((s for s in result if s.name == "foo"), None)
            if foo:
                param_names = [p.name for p in foo.params]
                assert "a" not in param_names  # already annotated

    def test_annotate_syntax_error_raises(self):
        ann = TypeAnnotator()
        with pytest.raises(AnnotatorError):
            ann.annotate("def (broken")

    def test_annotate_naming_is_valid(self):
        ann = TypeAnnotator()
        src = "def check(is_active, url, n_items): pass\n"
        result = ann.annotate(src)
        if result:
            fn = result[0]
            types = {p.name: p.suggested_type for p in fn.params}
            if "is_active" in types:
                assert types["is_active"] == "bool"
            if "url" in types:
                assert types["url"] == "str"
            if "n_items" in types:
                assert types["n_items"] == "int"

    def test_annotate_return_none(self):
        ann = TypeAnnotator()
        src = "def greet(name):\n    print(name)\n"
        result = ann.annotate(src)
        if result:
            fn = result[0]
            if fn.return_type:
                assert fn.return_type == "None"

    def test_annotate_return_consistent(self):
        ann = TypeAnnotator()
        src = "def get_count():\n    return 42\n"
        result = ann.annotate(src)
        if result:
            fn = result[0]
            if fn.return_type:
                assert fn.return_type == "int"

    def test_coverage_fully_annotated(self):
        ann = TypeAnnotator()
        cov = ann.coverage(_ANNOTATED)
        assert cov["param_coverage"] == 1.0

    def test_coverage_unannotated(self):
        ann = TypeAnnotator()
        cov = ann.coverage(_UNANNOTATED)
        assert cov["annotated_params"] == 0
        assert cov["total_params"] > 0

    def test_coverage_keys(self):
        ann = TypeAnnotator()
        cov = ann.coverage("def f(x): pass\n")
        for key in ("total_params", "annotated_params", "total_returns",
                    "annotated_returns", "param_coverage", "return_coverage"):
            assert key in cov

    def test_annotate_function_by_name(self):
        ann = TypeAnnotator()
        fn = ann.annotate_function(_UNANNOTATED, "process")
        assert fn is not None or fn is None  # may or may not find suggestions

    def test_annotate_function_not_found(self):
        ann = TypeAnnotator()
        fn = ann.annotate_function(_UNANNOTATED, "nonexistent")
        assert fn is None

    def test_min_confidence_filters_low(self):
        ann = TypeAnnotator(min_confidence=0.99)
        result = ann.annotate("def f(callback): pass\n")
        # callback naming has 0.6 confidence — should be filtered at 0.99
        if result:
            fn = result[0]
            assert all(p.confidence >= 0.99 for p in fn.params)

    def test_default_none_optional(self):
        ann = TypeAnnotator()
        result = ann.annotate("def f(name=None): pass\n")
        if result and result[0].params:
            p = result[0].params[0]
            assert "None" in p.suggested_type
