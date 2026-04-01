"""Tests for lidco.bootstrap.deferred — DeferredInitializer."""

from __future__ import annotations

import unittest

from lidco.bootstrap.deferred import (
    CircularDependencyError,
    DeferredInitializer,
    DeferredModule,
    ModuleNotRegisteredError,
)


class TestDeferredInitializer(unittest.TestCase):
    def test_register_and_list_modules(self) -> None:
        di = DeferredInitializer()
        di.register("a", lambda: "A")
        di.register("b", lambda: "B")
        assert di.list_modules() == ["a", "b"]

    def test_resolve_lazy(self) -> None:
        calls: list[str] = []

        def factory() -> str:
            calls.append("called")
            return "value"

        di = DeferredInitializer()
        di.register("mod", factory)
        assert not di.is_initialized("mod")
        result = di.resolve("mod")
        assert result == "value"
        assert di.is_initialized("mod")
        assert len(calls) == 1
        # Second resolve returns cached
        result2 = di.resolve("mod")
        assert result2 == "value"
        assert len(calls) == 1

    def test_resolve_not_registered(self) -> None:
        di = DeferredInitializer()
        with self.assertRaises(ModuleNotRegisteredError):
            di.resolve("nope")

    def test_depends_on_chain(self) -> None:
        order: list[str] = []
        di = DeferredInitializer()
        di.register("c", lambda: order.append("c") or "C", depends_on=("b",))
        di.register("b", lambda: order.append("b") or "B", depends_on=("a",))
        di.register("a", lambda: order.append("a") or "A")
        result = di.resolve("c")
        assert result == "C"
        assert order == ["a", "b", "c"]
        assert di.list_initialized() == ["c", "b", "a"]

    def test_circular_dependency_detected(self) -> None:
        di = DeferredInitializer()
        di.register("x", lambda: "X", depends_on=("y",))
        di.register("y", lambda: "Y", depends_on=("x",))
        assert di.has_circular() is True

    def test_no_circular_dependency(self) -> None:
        di = DeferredInitializer()
        di.register("a", lambda: "A")
        di.register("b", lambda: "B", depends_on=("a",))
        assert di.has_circular() is False

    def test_circular_raises_on_resolve(self) -> None:
        di = DeferredInitializer()
        di.register("x", lambda: "X", depends_on=("y",))
        di.register("y", lambda: "Y", depends_on=("x",))
        with self.assertRaises(CircularDependencyError):
            di.resolve("x")

    def test_reset_single(self) -> None:
        di = DeferredInitializer()
        di.register("a", lambda: "A")
        di.resolve("a")
        assert di.is_initialized("a")
        di.reset("a")
        assert not di.is_initialized("a")

    def test_reset_all(self) -> None:
        di = DeferredInitializer()
        di.register("a", lambda: "A")
        di.register("b", lambda: "B")
        di.resolve("a")
        di.resolve("b")
        di.reset()
        assert di.list_initialized() == []

    def test_list_initialized(self) -> None:
        di = DeferredInitializer()
        di.register("a", lambda: "A")
        di.register("b", lambda: "B")
        assert di.list_initialized() == []
        di.resolve("a")
        assert di.list_initialized() == ["a"]


if __name__ == "__main__":
    unittest.main()
