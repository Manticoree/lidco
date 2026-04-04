"""Tests for SessionTemplate and TemplateStore."""
from __future__ import annotations

import json
import unittest

from lidco.presets.template import SessionTemplate, TemplateStore


class TestSessionTemplate(unittest.TestCase):
    def test_defaults(self):
        t = SessionTemplate(name="test")
        self.assertEqual(t.name, "test")
        self.assertEqual(t.description, "")
        self.assertEqual(t.system_prompt, "")
        self.assertEqual(t.tools, [])
        self.assertEqual(t.config, {})
        self.assertEqual(t.tags, [])
        self.assertEqual(t.version, 1)

    def test_custom_values(self):
        t = SessionTemplate(
            name="custom",
            description="A custom template",
            system_prompt="Be helpful",
            tools=["read", "edit"],
            config={"model": "opus"},
            tags=["dev"],
            version=2,
        )
        self.assertEqual(t.description, "A custom template")
        self.assertEqual(t.tools, ["read", "edit"])
        self.assertEqual(t.config["model"], "opus")
        self.assertEqual(t.version, 2)


class TestTemplateStore(unittest.TestCase):
    def setUp(self):
        self.store = TemplateStore()
        self.t1 = SessionTemplate(name="a", description="Alpha", tags=["dev"])
        self.t2 = SessionTemplate(name="b", description="Beta", tags=["dev", "test"])
        self.t3 = SessionTemplate(name="c", description="Gamma", tags=["test"])

    def test_register_and_get(self):
        ret = self.store.register(self.t1)
        self.assertIs(ret, self.t1)
        self.assertIs(self.store.get("a"), self.t1)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nope"))

    def test_remove(self):
        self.store.register(self.t1)
        self.assertTrue(self.store.remove("a"))
        self.assertIsNone(self.store.get("a"))

    def test_remove_missing(self):
        self.assertFalse(self.store.remove("nope"))

    def test_find_by_tag(self):
        self.store.register(self.t1)
        self.store.register(self.t2)
        self.store.register(self.t3)
        dev = self.store.find_by_tag("dev")
        self.assertEqual([t.name for t in dev], ["a", "b"])

    def test_all_templates(self):
        self.store.register(self.t1)
        self.store.register(self.t2)
        self.assertEqual(len(self.store.all_templates()), 2)

    def test_export_and_import(self):
        self.store.register(self.t1)
        exported = self.store.export("a")
        data = json.loads(exported)
        self.assertEqual(data["name"], "a")
        # Import into a fresh store
        store2 = TemplateStore()
        imported = store2.import_template(exported)
        self.assertEqual(imported.name, "a")
        self.assertEqual(imported.description, "Alpha")

    def test_export_missing_raises(self):
        with self.assertRaises(KeyError):
            self.store.export("nope")

    def test_summary(self):
        self.store.register(self.t1)
        self.store.register(self.t2)
        s = self.store.summary()
        self.assertEqual(s["total"], 2)
        self.assertIn("a", s["names"])
        self.assertIn("b", s["names"])


if __name__ == "__main__":
    unittest.main()
