"""Tests for src/lidco/core/container.py — Container, CircularDependencyError."""
import pytest
from lidco.core.container import Container, CircularDependencyError


class TestContainerBasic:
    def test_register_and_resolve_value(self):
        c = Container()
        c.register("cfg", {"debug": True})
        assert c.resolve("cfg") == {"debug": True}

    def test_register_and_resolve_factory(self):
        c = Container()
        c.register("svc", lambda: "hello")
        assert c.resolve("svc") == "hello"

    def test_resolve_unknown_raises(self):
        c = Container()
        with pytest.raises(KeyError):
            c.resolve("unknown")

    def test_singleton_returns_same_instance(self):
        c = Container()
        c.register("svc", list, singleton=True)
        a = c.resolve("svc")
        b = c.resolve("svc")
        assert a is b

    def test_non_singleton_creates_new(self):
        c = Container()
        c.register("svc", list, singleton=False)
        a = c.resolve("svc")
        b = c.resolve("svc")
        assert a is not b

    def test_re_register_clears_singleton(self):
        c = Container()
        c.register("svc", list, singleton=True)
        a = c.resolve("svc")
        c.register("svc", list, singleton=True)
        b = c.resolve("svc")
        assert a is not b

    def test_is_registered(self):
        c = Container()
        c.register("x", 1)
        assert c.is_registered("x")
        assert not c.is_registered("y")

    def test_names(self):
        c = Container()
        c.register("b", 2)
        c.register("a", 1)
        assert c.names() == ["a", "b"]

    def test_clear(self):
        c = Container()
        c.register("x", 1)
        c.clear()
        with pytest.raises(KeyError):
            c.resolve("x")


class TestContainerAutowiring:
    def test_factory_params_resolved(self):
        c = Container()
        c.register("name", "Alice")

        def make_greeting(name):
            return f"Hello, {name}!"

        c.register("greeting", make_greeting, singleton=False)
        assert c.resolve("greeting") == "Hello, Alice!"

    def test_params_with_defaults_not_resolved(self):
        c = Container()
        calls = []

        def make_svc(x=99):
            calls.append(x)
            return x

        c.register("svc", make_svc, singleton=False)
        c.resolve("svc")
        assert calls == [99]

    def test_unregistered_param_not_injected(self):
        c = Container()

        def factory(unknown_param=None):
            return unknown_param

        c.register("svc", factory, singleton=False)
        result = c.resolve("svc")
        assert result is None


class TestCircularDependency:
    def test_circular_raises(self):
        c = Container()

        def a_factory(b):
            return "a"

        def b_factory(a):
            return "b"

        c.register("a", a_factory, singleton=False)
        c.register("b", b_factory, singleton=False)
        with pytest.raises(CircularDependencyError) as exc_info:
            c.resolve("a")
        assert "a" in exc_info.value.chain or "b" in exc_info.value.chain

    def test_circular_error_has_chain(self):
        c = Container()

        def x_factory(y): return "x"
        def y_factory(x): return "y"

        c.register("x", x_factory, singleton=False)
        c.register("y", y_factory, singleton=False)
        try:
            c.resolve("x")
        except CircularDependencyError as e:
            assert len(e.chain) >= 2


class TestContainerInjectDecorator:
    def test_inject_resolves_params(self):
        c = Container()
        c.register("name", "Bob")

        @c.inject
        def greet(name):
            return f"Hi {name}"

        assert greet() == "Hi Bob"

    def test_inject_kwargs_override(self):
        c = Container()
        c.register("name", "Bob")

        @c.inject
        def greet(name):
            return f"Hi {name}"

        assert greet(name="Alice") == "Hi Alice"

    def test_inject_positional_not_overridden(self):
        c = Container()
        c.register("x", 10)

        @c.inject
        def fn(x):
            return x

        assert fn(99) == 99
