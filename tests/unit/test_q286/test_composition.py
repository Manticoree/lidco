"""Tests for ToolComposition."""
from __future__ import annotations

import unittest

from lidco.tool_opt.composition import Pipeline, PipelineStep, ToolComposition


class TestPipelineStep(unittest.TestCase):
    def test_defaults(self):
        s = PipelineStep(tool="Read")
        self.assertEqual(s.tool, "Read")
        self.assertEqual(s.args, {})
        self.assertIsNone(s.transform)
        self.assertEqual(s.name, "Read")

    def test_custom_name(self):
        s = PipelineStep(tool="Read", name="read-file")
        self.assertEqual(s.name, "read-file")


class TestPipeline(unittest.TestCase):
    def test_empty(self):
        p = Pipeline()
        self.assertEqual(p.steps, [])
        self.assertEqual(p.name, "pipeline")


class TestToolComposition(unittest.TestCase):
    def setUp(self):
        self.tc = ToolComposition()

    def test_add_step(self):
        step = self.tc.add_step("Read", {"path": "a.py"})
        self.assertIsInstance(step, PipelineStep)
        self.assertEqual(step.tool, "Read")

    def test_chain_empty(self):
        p = self.tc.chain()
        self.assertEqual(len(p.steps), 0)

    def test_chain_with_steps(self):
        self.tc.add_step("Read")
        self.tc.add_step("Edit")
        p = self.tc.chain()
        self.assertEqual(len(p.steps), 2)
        self.assertEqual(p.steps[0].tool, "Read")

    def test_chain_explicit_steps(self):
        s1 = PipelineStep(tool="A")
        s2 = PipelineStep(tool="B")
        p = self.tc.chain([s1, s2])
        self.assertEqual(len(p.steps), 2)

    def test_clear(self):
        self.tc.add_step("Read")
        self.tc.clear()
        p = self.tc.chain()
        self.assertEqual(len(p.steps), 0)

    def test_execute_simple(self):
        self.tc.register_tool("double", lambda x=0, **kw: x * 2)
        step = self.tc.add_step("double", {"x": 5})
        pipeline = self.tc.chain()
        result = self.tc.execute(pipeline)
        self.assertEqual(result, 10)

    def test_execute_chain_threading(self):
        self.tc.register_tool("inc", lambda _last_result=0, **kw: _last_result + 1)
        self.tc.add_step("inc")
        self.tc.add_step("inc")
        self.tc.add_step("inc")
        pipeline = self.tc.chain()
        result = self.tc.execute(pipeline)
        self.assertEqual(result, 3)

    def test_execute_with_transform(self):
        self.tc.register_tool("value", lambda v=0, **kw: v)
        self.tc.add_step("value", {"v": 5}, transform=lambda x: x * 10)
        pipeline = self.tc.chain()
        result = self.tc.execute(pipeline)
        self.assertEqual(result, 50)

    def test_execute_unknown_tool_raises(self):
        self.tc.add_step("nonexistent")
        pipeline = self.tc.chain()
        with self.assertRaises(ValueError) as cm:
            self.tc.execute(pipeline)
        self.assertIn("nonexistent", str(cm.exception))

    def test_execute_with_context(self):
        self.tc.register_tool("greet", lambda name="world", **kw: f"hello {name}")
        self.tc.add_step("greet")
        pipeline = self.tc.chain()
        result = self.tc.execute(pipeline, {"name": "test"})
        self.assertEqual(result, "hello test")

    def test_register_tool(self):
        self.tc.register_tool("noop", lambda **kw: None)
        # Should not raise when executing
        self.tc.add_step("noop")
        pipeline = self.tc.chain()
        result = self.tc.execute(pipeline)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
