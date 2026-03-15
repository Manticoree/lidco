"""Tests for ApiExtractor — Task 350."""

from __future__ import annotations

import pytest

from lidco.analysis.api_extractor import ApiExtractor, ApiFunction, ApiParam, ApiReport


SIMPLE_SOURCE = '''\
def greet(name: str, greeting: str = "Hello") -> str:
    """Return a greeting."""
    return f"{greeting}, {name}!"

async def fetch(url: str) -> bytes:
    pass
'''

CLASS_SOURCE = '''\
class MyService:
    """A service class."""

    def __init__(self, host: str, port: int = 8080) -> None:
        self.host = host

    def connect(self) -> bool:
        """Connect to the service."""
        pass

    def _private_method(self):
        pass
'''

NO_ANNOTATIONS = '''\
def add(a, b):
    return a + b
'''

SYNTAX_ERROR = "def broken(:"

VARARGS_SOURCE = '''\
def variadic(*args: int, key: str = "default", **kwargs: float) -> None:
    pass
'''


class TestApiParam:
    def test_frozen(self):
        p = ApiParam(name="x", annotation="int", default="", kind="positional")
        with pytest.raises((AttributeError, TypeError)):
            p.name = "y"  # type: ignore[misc]


class TestApiFunction:
    def test_frozen(self):
        fn = ApiFunction(
            name="f", file="x.py", line=1, params=(),
            return_annotation="", docstring="",
        )
        with pytest.raises((AttributeError, TypeError)):
            fn.name = "g"  # type: ignore[misc]


class TestApiExtractor:
    def setup_method(self):
        self.extractor = ApiExtractor()

    def test_empty_source(self):
        report = self.extractor.extract("")
        assert len(report.functions) == 0

    def test_syntax_error(self):
        report = self.extractor.extract(SYNTAX_ERROR)
        assert len(report.functions) == 0

    def test_finds_functions(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        names = {f.name for f in report.functions}
        assert "greet" in names
        assert "fetch" in names

    def test_async_function_detected(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        fetch = next(f for f in report.functions if f.name == "fetch")
        assert fetch.is_async is True

    def test_sync_function_not_async(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        assert greet.is_async is False

    def test_params_extracted(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        param_names = [p.name for p in greet.params]
        assert "name" in param_names
        assert "greeting" in param_names

    def test_param_annotation(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        name_param = next(p for p in greet.params if p.name == "name")
        assert name_param.annotation == "str"

    def test_param_default(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        greeting_param = next(p for p in greet.params if p.name == "greeting")
        assert "'Hello'" in greeting_param.default or '"Hello"' in greeting_param.default

    def test_return_annotation(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        assert greet.return_annotation == "str"

    def test_docstring_extracted(self):
        report = self.extractor.extract(SIMPLE_SOURCE)
        greet = next(f for f in report.functions if f.name == "greet")
        assert "greeting" in greet.docstring.lower() or greet.docstring

    def test_no_annotation_empty_string(self):
        report = self.extractor.extract(NO_ANNOTATIONS)
        fn = report.functions[0]
        assert fn.return_annotation == ""

    def test_class_methods_indexed(self):
        report = self.extractor.extract(CLASS_SOURCE)
        methods = [f for f in report.functions if f.is_method]
        method_names = {m.name for m in methods}
        assert "__init__" in method_names
        assert "connect" in method_names

    def test_self_removed_from_params(self):
        report = self.extractor.extract(CLASS_SOURCE)
        connect = next(f for f in report.functions if f.name == "connect")
        param_names = [p.name for p in connect.params]
        assert "self" not in param_names

    def test_class_name_set(self):
        report = self.extractor.extract(CLASS_SOURCE)
        connect = next(f for f in report.functions if f.name == "connect")
        assert connect.class_name == "MyService"

    def test_classes_list(self):
        report = self.extractor.extract(CLASS_SOURCE)
        assert "MyService" in report.classes

    def test_public_functions_filter(self):
        report = self.extractor.extract(CLASS_SOURCE)
        public = report.public_functions()
        names = {f.name for f in public}
        assert "_private_method" not in names

    def test_varargs_extracted(self):
        report = self.extractor.extract(VARARGS_SOURCE)
        fn = report.functions[0]
        param_names = [p.name for p in fn.params]
        assert any("args" in n for n in param_names)
        assert any("kwargs" in n for n in param_names)

    def test_file_path_recorded(self):
        report = self.extractor.extract(SIMPLE_SOURCE, file_path="svc.py")
        assert all(f.file == "svc.py" for f in report.functions)
