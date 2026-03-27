"""Tests for src/lidco/testing/mock_gen.py."""
import pytest

from lidco.testing.mock_gen import (
    ClassMockSpec, GeneratedMock, MethodStub, MockGenError, MockGenerator,
)

_SIMPLE = """\
class UserService:
    def get_user(self, user_id: int) -> dict:
        ...
    def create_user(self, name: str) -> bool:
        ...
"""

_ASYNC = """\
class ApiClient:
    async def fetch(self, url: str) -> list:
        ...
    async def post(self, data: dict) -> dict:
        ...
"""

_WITH_ATTRS = """\
class Repo:
    db: object
    cache: object
    def find(self, id: int) -> dict:
        ...
"""

_EMPTY = """\
class Empty:
    pass
"""


class TestMethodStub:
    def test_mock_attr(self):
        m = MethodStub(name="get_user")
        assert "get_user" in m.mock_attr()

    def test_mock_setup_sync(self):
        m = MethodStub(name="find", return_type="dict")
        setup = m.mock_setup("mock")
        assert "mock.find" in setup
        assert "return_value" in setup

    def test_mock_setup_async(self):
        m = MethodStub(name="fetch", is_async=True)
        setup = m.mock_setup("mock")
        assert "AsyncMock" in setup

    def test_init_returns_empty(self):
        m = MethodStub(name="__init__")
        assert m.mock_setup() == ""

    def test_default_return_str(self):
        m = MethodStub(name="f", return_type="str")
        assert '"' in m._default_return()

    def test_default_return_bool(self):
        m = MethodStub(name="f", return_type="bool")
        assert m._default_return() == "True"

    def test_default_return_list(self):
        m = MethodStub(name="f", return_type="list")
        assert m._default_return() == "[]"

    def test_default_return_none(self):
        m = MethodStub(name="f", return_type="None")
        assert m._default_return() == "None"

    def test_default_return_unknown(self):
        assert "MagicMock" in MethodStub(name="f", return_type="MyType")._default_return()


class TestMockGenerator:
    def test_parse_class(self):
        gen = MockGenerator()
        specs = gen.parse_classes(_SIMPLE)
        assert any(s.class_name == "UserService" for s in specs)

    def test_parse_methods(self):
        gen = MockGenerator()
        specs = gen.parse_classes(_SIMPLE)
        user_svc = next(s for s in specs if s.class_name == "UserService")
        names = [m.name for m in user_svc.methods]
        assert "get_user" in names
        assert "create_user" in names

    def test_parse_async(self):
        gen = MockGenerator()
        specs = gen.parse_classes(_ASYNC)
        client = next(s for s in specs if s.class_name == "ApiClient")
        assert all(m.is_async for m in client.methods)

    def test_parse_attributes(self):
        gen = MockGenerator()
        specs = gen.parse_classes(_WITH_ATTRS)
        repo = next(s for s in specs if s.class_name == "Repo")
        assert "db" in repo.attributes
        assert "cache" in repo.attributes

    def test_parse_syntax_error(self):
        gen = MockGenerator()
        with pytest.raises(MockGenError):
            gen.parse_classes("def (broken")

    def test_generate_returns_list(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        assert isinstance(mocks, list)
        assert len(mocks) == 1

    def test_generate_mock_var(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        m = mocks[0]
        assert "userservice" in m.mock_var.lower()

    def test_generate_setup_has_magicmock(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        assert "MagicMock" in mocks[0].setup_code

    def test_generate_setup_has_methods(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        assert "get_user" in mocks[0].setup_code

    def test_generate_imports_async(self):
        gen = MockGenerator()
        mocks = gen.generate(_ASYNC)
        assert "AsyncMock" in mocks[0].imports[0]

    def test_generate_fixture_code(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        assert "@pytest.fixture" in mocks[0].fixture_code

    def test_generate_patch_decorator(self):
        gen = MockGenerator()
        mocks = gen.generate(_SIMPLE)
        assert "@patch(" in mocks[0].patch_decorator

    def test_generate_for_class_found(self):
        gen = MockGenerator()
        m = gen.generate_for_class(_SIMPLE, "UserService")
        assert m is not None
        assert m.class_name == "UserService"

    def test_generate_for_class_not_found(self):
        gen = MockGenerator()
        m = gen.generate_for_class(_SIMPLE, "Ghost")
        assert m is None

    def test_generate_patch_test(self):
        gen = MockGenerator()
        code = gen.generate_patch_test(_SIMPLE, "UserService")
        assert "@patch" in code or "patch" in code.lower()

    def test_generate_patch_test_not_found(self):
        gen = MockGenerator()
        code = gen.generate_patch_test(_SIMPLE, "Ghost")
        assert "not found" in code.lower() or "#" in code

    def test_empty_class(self):
        gen = MockGenerator()
        mocks = gen.generate(_EMPTY)
        assert len(mocks) == 1
        assert "Empty" in mocks[0].setup_code

    def test_public_methods_filter(self):
        gen = MockGenerator()
        specs = gen.parse_classes(_SIMPLE)
        s = specs[0]
        pub = s.public_methods()
        assert all(not m.name.startswith("_") for m in pub)

    def test_module_path_in_patch(self):
        gen = MockGenerator(module_path="myapp.services")
        mocks = gen.generate(_SIMPLE)
        assert "myapp.services" in mocks[0].patch_decorator
