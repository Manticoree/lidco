"""Tests for Q131 PromptChain."""
from __future__ import annotations
import unittest
from lidco.prompts.chain_builder import PromptChain, ChainStep, ChainResult
from lidco.prompts.template_engine import PromptTemplateEngine


class TestChainStep(unittest.TestCase):
    def test_defaults(self):
        step = ChainStep(name="s1", template="t", output_key="out")
        self.assertFalse(step.stop_if_empty)


class TestChainResult(unittest.TestCase):
    def test_fields(self):
        r = ChainResult(steps_run=2, outputs={"k": "v"}, final_output="v")
        self.assertEqual(r.steps_run, 2)
        self.assertEqual(r.final_output, "v")


class TestPromptChain(unittest.TestCase):
    def setUp(self):
        self.chain = PromptChain()

    def _execute(self, prompt: str) -> str:
        return f"[response to: {prompt[:20]}]"

    def test_single_step(self):
        self.chain.add_step(ChainStep(name="s1", template="Summarize {{text}}", output_key="summary"))
        result = self.chain.run({"text": "hello world"}, self._execute)
        self.assertEqual(result.steps_run, 1)
        self.assertIn("summary", result.outputs)

    def test_two_steps_forward_output(self):
        self.chain.add_step(ChainStep(name="s1", template="Step 1: {{text}}", output_key="step1"))
        self.chain.add_step(ChainStep(name="s2", template="Step 2: {{step1}}", output_key="step2"))
        result = self.chain.run({"text": "test"}, self._execute)
        self.assertEqual(result.steps_run, 2)
        self.assertIn("step1", result.outputs)
        self.assertIn("step2", result.outputs)

    def test_final_output(self):
        self.chain.add_step(ChainStep(name="s1", template="t1", output_key="o1"))
        self.chain.add_step(ChainStep(name="s2", template="t2", output_key="o2"))
        result = self.chain.run({}, self._execute)
        self.assertEqual(result.final_output, result.outputs["o2"])

    def test_stop_if_empty(self):
        self.chain.add_step(
            ChainStep(name="s1", template="check", output_key="check", stop_if_empty=True)
        )
        self.chain.add_step(ChainStep(name="s2", template="never", output_key="never"))

        def empty_exec(prompt: str) -> str:
            if "check" in prompt:
                return ""
            return "reached"

        result = self.chain.run({}, empty_exec)
        self.assertEqual(result.steps_run, 1)
        self.assertNotIn("never", result.outputs)

    def test_stop_if_empty_false_continues(self):
        self.chain.add_step(
            ChainStep(name="s1", template="check", output_key="check", stop_if_empty=False)
        )
        self.chain.add_step(ChainStep(name="s2", template="next", output_key="next"))

        def empty_exec(prompt: str) -> str:
            return ""

        result = self.chain.run({}, empty_exec)
        self.assertEqual(result.steps_run, 2)

    def test_empty_chain(self):
        result = self.chain.run({}, self._execute)
        self.assertEqual(result.steps_run, 0)
        self.assertEqual(result.final_output, "")

    def test_add_step_returns_self(self):
        result = self.chain.add_step(ChainStep(name="s", template="t", output_key="o"))
        self.assertIsInstance(result, PromptChain)

    def test_clear(self):
        self.chain.add_step(ChainStep(name="s", template="t", output_key="o"))
        self.chain.clear()
        result = self.chain.run({}, self._execute)
        self.assertEqual(result.steps_run, 0)

    def test_custom_engine(self):
        engine = PromptTemplateEngine()
        chain = PromptChain(engine=engine)
        chain.add_step(ChainStep(name="s", template="Hello {{name}}", output_key="greeting"))
        called_with = []

        def exec_fn(p: str) -> str:
            called_with.append(p)
            return "hi"

        chain.run({"name": "World"}, exec_fn)
        self.assertIn("Hello World", called_with[0])

    def test_variables_passed_forward(self):
        self.chain.add_step(ChainStep(name="s1", template="{{x}}", output_key="r1"))
        self.chain.add_step(ChainStep(name="s2", template="{{x}} and {{r1}}", output_key="r2"))
        called = []

        def exec_fn(p: str) -> str:
            called.append(p)
            return "done"

        self.chain.run({"x": "hello"}, exec_fn)
        self.assertIn("hello", called[0])
        self.assertIn("hello", called[1])

    def test_outputs_dict_keys(self):
        self.chain.add_step(ChainStep(name="step_a", template="t", output_key="key_a"))
        result = self.chain.run({}, lambda p: "val")
        self.assertIn("key_a", result.outputs)
        self.assertEqual(result.outputs["key_a"], "val")


if __name__ == "__main__":
    unittest.main()
