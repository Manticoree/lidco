"""Tests for Q131 CLI commands."""
from __future__ import annotations
import asyncio
import json
import unittest
from lidco.cli.commands import q131_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ131Commands(unittest.TestCase):
    def setUp(self):
        q131_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q131_cmds.register(MockRegistry())
        self.handler = self.registered["prompt"].handler

    def test_command_registered(self):
        self.assertIn("prompt", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- render ---

    def test_render_basic(self):
        vars_json = json.dumps({"name": "World"})
        result = _run(self.handler(f'render {vars_json} Hello {{{{name}}}}!'))
        self.assertIn("Hello World!", result)

    def test_render_invalid_json(self):
        result = _run(self.handler('render {bad} template'))
        self.assertIn("Invalid JSON", result)

    def test_render_missing_args(self):
        result = _run(self.handler('render'))
        self.assertIn("Usage", result)

    def test_render_multiple_vars(self):
        vars_json = json.dumps({"x": "1", "y": "2"})
        result = _run(self.handler(f'render {vars_json} {{{{x}}}} plus {{{{y}}}}'))
        self.assertIn("1 plus 2", result)

    # --- build ---

    def test_build_basic(self):
        msgs = json.dumps([{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "Hi"}])
        result = _run(self.handler(f'build {msgs}'))
        self.assertIn("You are helpful.", result)
        self.assertIn("Hi", result)

    def test_build_invalid_json(self):
        result = _run(self.handler('build {invalid}'))
        self.assertIn("Invalid JSON", result)

    def test_build_missing_args(self):
        result = _run(self.handler('build'))
        self.assertIn("Usage", result)

    def test_build_assistant_role(self):
        msgs = json.dumps([{"role": "assistant", "content": "Sure!"}])
        result = _run(self.handler(f'build {msgs}'))
        self.assertIn("Sure!", result)

    # --- examples ---

    def test_examples_basic(self):
        pairs = json.dumps([{"input": "hello", "output": "world"}])
        result = _run(self.handler(f'examples {pairs}'))
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_examples_invalid_json(self):
        result = _run(self.handler('examples {bad}'))
        self.assertIn("Invalid JSON", result)

    def test_examples_missing_args(self):
        result = _run(self.handler('examples'))
        self.assertIn("Usage", result)

    def test_examples_qa_format(self):
        pairs = json.dumps([{"input": "q1", "output": "a1"}])
        result = _run(self.handler(f'examples {pairs}'))
        self.assertIn("Q:", result)
        self.assertIn("A:", result)

    # --- chain ---

    def test_chain_basic(self):
        steps = json.dumps([{"name": "s1", "template": "Hello {{topic}}", "output_key": "r1"}])
        vars_ = json.dumps({"topic": "world"})
        result = _run(self.handler(f'chain {steps} {vars_}'))
        self.assertIn("Steps run: 1", result)

    def test_chain_invalid_json(self):
        result = _run(self.handler('chain {bad} {}'))
        self.assertIn("Invalid JSON", result)

    def test_chain_missing_args(self):
        result = _run(self.handler('chain'))
        self.assertIn("Usage", result)

    def test_chain_shows_outputs(self):
        steps = json.dumps([{"name": "s1", "template": "t", "output_key": "result"}])
        vars_ = json.dumps({})
        result = _run(self.handler(f'chain {steps} {vars_}'))
        self.assertIn("result:", result)

    def test_command_description(self):
        self.assertIn("Q131", self.registered["prompt"].description)


if __name__ == "__main__":
    unittest.main()
