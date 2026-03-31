"""Tests for Q131 PromptBuilder."""
from __future__ import annotations
import unittest
from lidco.prompts.prompt_builder import PromptBuilder


class TestPromptBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = PromptBuilder()

    def test_system_message(self):
        result = self.builder.system("You are helpful.").build()
        self.assertIn("You are helpful.", result)
        self.assertIn("SYSTEM", result)

    def test_user_message(self):
        result = self.builder.user("Hello!").build()
        self.assertIn("Hello!", result)
        self.assertIn("USER", result)

    def test_assistant_message(self):
        result = self.builder.assistant("Hi there!").build()
        self.assertIn("Hi there!", result)
        self.assertIn("ASSISTANT", result)

    def test_multiple_messages(self):
        result = self.builder.system("sys").user("usr").assistant("ast").build()
        self.assertIn("sys", result)
        self.assertIn("usr", result)
        self.assertIn("ast", result)

    def test_context_block(self):
        result = self.builder.context("code", "print('hello')").build()
        self.assertIn("<code>", result)
        self.assertIn("print('hello')", result)
        self.assertIn("</code>", result)

    def test_examples(self):
        result = self.builder.examples([("input1", "output1"), ("input2", "output2")]).build()
        self.assertIn("input1", result)
        self.assertIn("output1", result)
        self.assertIn("Input:", result)
        self.assertIn("Output:", result)

    def test_instructions(self):
        result = self.builder.instructions("Do this carefully.").build()
        self.assertIn("Do this carefully.", result)

    def test_build_messages(self):
        msgs = self.builder.system("sys").user("usr").build_messages()
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[0]["content"], "sys")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[1]["content"], "usr")

    def test_reset(self):
        self.builder.system("hello")
        self.builder.reset()
        result = self.builder.build()
        self.assertEqual(result, "")

    def test_reset_returns_self(self):
        result = self.builder.reset()
        self.assertIsInstance(result, PromptBuilder)

    def test_fluent_chaining(self):
        result = self.builder.system("a").user("b").assistant("c")
        self.assertIsInstance(result, PromptBuilder)

    def test_token_estimate_empty(self):
        self.assertEqual(self.builder.token_estimate(), 0)

    def test_token_estimate_nonempty(self):
        self.builder.user("Hello world")
        est = self.builder.token_estimate()
        self.assertGreater(est, 0)

    def test_token_estimate_custom_ratio(self):
        self.builder.user("1234")  # 4 chars
        est = self.builder.token_estimate(chars_per_token=2.0)
        self.assertEqual(est, 2)

    def test_build_messages_assistant(self):
        msgs = self.builder.assistant("yes").build_messages()
        self.assertEqual(msgs[0]["role"], "assistant")

    def test_context_returns_self(self):
        result = self.builder.context("lbl", "val")
        self.assertIsInstance(result, PromptBuilder)

    def test_examples_returns_self(self):
        result = self.builder.examples([])
        self.assertIsInstance(result, PromptBuilder)

    def test_instructions_returns_self(self):
        result = self.builder.instructions("do it")
        self.assertIsInstance(result, PromptBuilder)

    def test_build_messages_empty(self):
        self.assertEqual(self.builder.build_messages(), [])

    def test_multiple_context_blocks(self):
        result = self.builder.context("a", "1").context("b", "2").build()
        self.assertIn("<a>", result)
        self.assertIn("<b>", result)


if __name__ == "__main__":
    unittest.main()
