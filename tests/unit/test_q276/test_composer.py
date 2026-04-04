"""Tests for PresetComposer."""
from __future__ import annotations

import unittest

from lidco.presets.composer import PresetComposer
from lidco.presets.library import Preset, PresetLibrary
from lidco.presets.template import SessionTemplate


class TestPresetComposer(unittest.TestCase):
    def setUp(self):
        self.lib = PresetLibrary()
        self.composer = PresetComposer(self.lib)

    def test_extend_basic(self):
        tmpl = self.composer.extend("bug-fix", {"description": "My debug"}, "my-debug")
        self.assertEqual(tmpl.name, "my-debug")
        self.assertEqual(tmpl.description, "My debug")
        # Inherits tools from bug-fix
        self.assertIn("read", tmpl.tools)

    def test_extend_preserves_base_when_no_override(self):
        tmpl = self.composer.extend("feature", {}, "my-feature")
        base = self.lib.get("feature").template
        self.assertEqual(tmpl.system_prompt, base.system_prompt)
        self.assertEqual(tmpl.tags, base.tags)

    def test_extend_config_merge(self):
        base_t = SessionTemplate(name="conf", config={"a": 1, "b": 2})
        self.lib.add(Preset(name="conf", category="dev", template=base_t))
        tmpl = self.composer.extend("conf", {"config": {"b": 99, "c": 3}}, "merged")
        self.assertEqual(tmpl.config, {"a": 1, "b": 99, "c": 3})

    def test_extend_missing_raises(self):
        with self.assertRaises(KeyError):
            self.composer.extend("nope", {}, "x")

    def test_merge(self):
        tmpl = self.composer.merge("bug-fix", "review", "debug-review")
        self.assertEqual(tmpl.name, "debug-review")
        # Review overrides description
        self.assertIn("Review", tmpl.description)
        # Tools from both
        self.assertIn("read", tmpl.tools)
        self.assertIn("grep", tmpl.tools)

    def test_merge_deduplicates_tools(self):
        tmpl = self.composer.merge("bug-fix", "feature", "combined")
        # Both have "read" — should appear once
        self.assertEqual(tmpl.tools.count("read"), 1)

    def test_merge_missing_raises(self):
        with self.assertRaises(KeyError):
            self.composer.merge("nope", "bug-fix", "x")
        with self.assertRaises(KeyError):
            self.composer.merge("bug-fix", "nope", "x")

    def test_substitute(self):
        t = SessionTemplate(name="t", system_prompt="Hello {{name}}, you do {{task}}.")
        result = self.composer.substitute(t, {"name": "Alice", "task": "coding"})
        self.assertEqual(result.system_prompt, "Hello Alice, you do coding.")
        # Original unchanged
        self.assertIn("{{name}}", t.system_prompt)

    def test_substitute_no_vars(self):
        t = SessionTemplate(name="t", system_prompt="No vars here.")
        result = self.composer.substitute(t, {"foo": "bar"})
        self.assertEqual(result.system_prompt, "No vars here.")

    def test_preview(self):
        text = self.composer.preview("bug-fix")
        self.assertIn("bug-fix", text)
        self.assertIn("Category: development", text)
        self.assertIn("Author: system", text)

    def test_preview_missing_raises(self):
        with self.assertRaises(KeyError):
            self.composer.preview("nope")

    def test_summary(self):
        s = self.composer.summary()
        self.assertEqual(s["library_total"], 5)


if __name__ == "__main__":
    unittest.main()
