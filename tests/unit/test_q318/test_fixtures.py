"""Tests for lidco.testdata.fixtures (Task 1703)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.testdata.fixtures import (
    CleanupAction,
    FixtureDef,
    FixtureManager,
    FixtureScope,
    FixtureSet,
)


class TestFixtureDef(unittest.TestCase):
    def test_frozen(self) -> None:
        fd = FixtureDef("users")
        with self.assertRaises(AttributeError):
            fd.name = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        fd = FixtureDef("t")
        self.assertEqual(fd.scope, FixtureScope.TEST)
        self.assertEqual(fd.version, 1)
        self.assertEqual(fd.depends_on, ())
        self.assertEqual(fd.tags, ())

    def test_with_data(self) -> None:
        fd = FixtureDef("t", data={"a": 1})
        self.assertEqual(fd.data["a"], 1)


class TestFixtureScope(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(FixtureScope.TEST.value, "test")
        self.assertEqual(FixtureScope.MODULE.value, "module")
        self.assertEqual(FixtureScope.SESSION.value, "session")


class TestFixtureSet(unittest.TestCase):
    def test_names(self) -> None:
        fs = FixtureSet((FixtureDef("a"), FixtureDef("b")))
        self.assertEqual(fs.names, ["a", "b"])

    def test_get_found(self) -> None:
        fd = FixtureDef("x", data={"k": 1})
        fs = FixtureSet((fd,))
        self.assertIs(fs.get("x"), fd)

    def test_get_not_found(self) -> None:
        fs = FixtureSet(())
        self.assertIsNone(fs.get("missing"))


class TestCleanupAction(unittest.TestCase):
    def test_frozen(self) -> None:
        ca = CleanupAction("f", "delete")
        with self.assertRaises(AttributeError):
            ca.action = "x"  # type: ignore[misc]


class TestFixtureManager(unittest.TestCase):
    def test_register(self) -> None:
        mgr = FixtureManager().register(FixtureDef("a"))
        self.assertEqual(mgr.registered_names, ["a"])

    def test_register_many(self) -> None:
        mgr = FixtureManager().register_many([FixtureDef("a"), FixtureDef("b")])
        self.assertEqual(mgr.registered_names, ["a", "b"])

    def test_get(self) -> None:
        fd = FixtureDef("x")
        mgr = FixtureManager().register(fd)
        self.assertEqual(mgr.get("x"), fd)
        self.assertIsNone(mgr.get("missing"))

    def test_load_file(self) -> None:
        data = {
            "fixtures": [
                {"name": "users", "scope": "test", "data": {"a": 1}, "version": 2},
                {"name": "roles", "scope": "session", "depends_on": ["users"]},
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name

        try:
            mgr = FixtureManager()
            fset = mgr.load_file(path)
            self.assertEqual(len(fset.fixtures), 2)
            self.assertEqual(fset.fixtures[0].name, "users")
            self.assertEqual(fset.fixtures[0].version, 2)
            self.assertEqual(fset.fixtures[1].scope, FixtureScope.SESSION)
            self.assertEqual(fset.fixtures[1].depends_on, ("users",))
            self.assertEqual(fset.source, path)
        finally:
            os.unlink(path)

    def test_resolve_order_simple(self) -> None:
        mgr = (
            FixtureManager()
            .register(FixtureDef("a"))
            .register(FixtureDef("b", depends_on=("a",)))
            .register(FixtureDef("c", depends_on=("b",)))
        )
        order = mgr.resolve_order(["c"])
        self.assertEqual(order, ["a", "b", "c"])

    def test_resolve_order_all(self) -> None:
        mgr = (
            FixtureManager()
            .register(FixtureDef("x"))
            .register(FixtureDef("y", depends_on=("x",)))
        )
        order = mgr.resolve_order()
        self.assertEqual(order.index("x"), 0)

    def test_circular_dependency_raises(self) -> None:
        mgr = (
            FixtureManager()
            .register(FixtureDef("a", depends_on=("b",)))
            .register(FixtureDef("b", depends_on=("a",)))
        )
        with self.assertRaises(ValueError):
            mgr.resolve_order()

    def test_setup_and_teardown(self) -> None:
        mgr = (
            FixtureManager()
            .register(FixtureDef("a"))
            .register(FixtureDef("b", depends_on=("a",)))
        )
        activated = mgr.setup()
        self.assertEqual([f.name for f in activated], ["a", "b"])
        self.assertEqual(mgr.active_names, ["a", "b"])

        actions = mgr.teardown()
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].fixture_name, "b")  # reverse order
        self.assertEqual(actions[1].fixture_name, "a")
        self.assertEqual(mgr.active_names, [])

    def test_setup_subset(self) -> None:
        mgr = (
            FixtureManager()
            .register(FixtureDef("a"))
            .register(FixtureDef("b"))
        )
        activated = mgr.setup(["a"])
        self.assertEqual([f.name for f in activated], ["a"])

    def test_load_file_not_found(self) -> None:
        mgr = FixtureManager()
        with self.assertRaises(FileNotFoundError):
            mgr.load_file("/nonexistent/path.json")


if __name__ == "__main__":
    unittest.main()
