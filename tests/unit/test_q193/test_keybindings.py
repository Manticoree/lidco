"""Tests for KeyBinding and KeybindingRegistry."""
from __future__ import annotations

import json
import unittest

from lidco.input.keybindings import KeyBinding, KeybindingRegistry


class TestKeyBinding(unittest.TestCase):
    def test_frozen(self):
        kb = KeyBinding(keys=("ctrl", "s"), action="save")
        with self.assertRaises(AttributeError):
            kb.action = "quit"  # type: ignore[misc]

    def test_defaults(self):
        kb = KeyBinding(keys=("ctrl", "q"), action="quit")
        self.assertEqual(kb.description, "")
        self.assertEqual(kb.context, "global")

    def test_fields(self):
        kb = KeyBinding(keys=("ctrl", "shift", "p"), action="palette", description="Open palette", context="editor")
        self.assertEqual(kb.keys, ("ctrl", "shift", "p"))
        self.assertEqual(kb.action, "palette")
        self.assertEqual(kb.description, "Open palette")
        self.assertEqual(kb.context, "editor")


class TestRegistryInit(unittest.TestCase):
    def test_empty(self):
        r = KeybindingRegistry()
        self.assertEqual(len(r.bindings), 0)

    def test_with_bindings(self):
        kb = KeyBinding(keys=("a",), action="test")
        r = KeybindingRegistry((kb,))
        self.assertEqual(len(r.bindings), 1)


class TestBind(unittest.TestCase):
    def test_bind_returns_new_instance(self):
        r = KeybindingRegistry()
        r2 = r.bind(("ctrl", "s"), "save")
        self.assertIsNot(r, r2)
        self.assertEqual(len(r.bindings), 0)
        self.assertEqual(len(r2.bindings), 1)

    def test_bind_replaces_existing(self):
        r = KeybindingRegistry()
        r = r.bind(("ctrl", "s"), "save")
        r = r.bind(("ctrl", "s"), "save_all")
        self.assertEqual(len(r.bindings), 1)
        self.assertEqual(r.lookup(("ctrl", "s")).action, "save_all")

    def test_bind_with_description_and_context(self):
        r = KeybindingRegistry().bind(("ctrl", "z"), "undo", description="Undo last", context="editor")
        b = r.lookup(("ctrl", "z"))
        self.assertEqual(b.description, "Undo last")
        self.assertEqual(b.context, "editor")


class TestUnbind(unittest.TestCase):
    def test_unbind_removes_binding(self):
        r = KeybindingRegistry().bind(("ctrl", "s"), "save")
        r2 = r.unbind(("ctrl", "s"))
        self.assertIsNot(r, r2)
        self.assertEqual(len(r.bindings), 1)
        self.assertEqual(len(r2.bindings), 0)

    def test_unbind_nonexistent_is_noop(self):
        r = KeybindingRegistry().bind(("a",), "action")
        r2 = r.unbind(("b",))
        self.assertEqual(len(r2.bindings), 1)


class TestLookup(unittest.TestCase):
    def test_lookup_found(self):
        r = KeybindingRegistry().bind(("ctrl", "c"), "copy")
        b = r.lookup(("ctrl", "c"))
        self.assertIsNotNone(b)
        self.assertEqual(b.action, "copy")

    def test_lookup_not_found(self):
        r = KeybindingRegistry()
        self.assertIsNone(r.lookup(("x",)))


class TestConflicts(unittest.TestCase):
    def test_no_conflicts(self):
        r = KeybindingRegistry().bind(("a",), "x").bind(("b",), "y")
        self.assertEqual(r.conflicts(), [])

    def test_detects_conflicts(self):
        kb1 = KeyBinding(keys=("a",), action="x")
        kb2 = KeyBinding(keys=("a",), action="y")
        r = KeybindingRegistry((kb1, kb2))
        conflicts = r.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0][0].action, "x")
        self.assertEqual(conflicts[0][1].action, "y")


class TestJsonRoundTrip(unittest.TestCase):
    def test_export_and_load(self):
        r = KeybindingRegistry().bind(("ctrl", "s"), "save", "Save file", "editor")
        exported = r.export_json()
        r2 = KeybindingRegistry.load_json(exported)
        self.assertEqual(len(r2.bindings), 1)
        b = r2.bindings[0]
        self.assertEqual(b.keys, ("ctrl", "s"))
        self.assertEqual(b.action, "save")
        self.assertEqual(b.description, "Save file")
        self.assertEqual(b.context, "editor")

    def test_export_valid_json(self):
        r = KeybindingRegistry().bind(("x",), "test")
        data = json.loads(r.export_json())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_load_empty(self):
        r = KeybindingRegistry.load_json("[]")
        self.assertEqual(len(r.bindings), 0)


if __name__ == "__main__":
    unittest.main()
