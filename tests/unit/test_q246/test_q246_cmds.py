"""Tests for Q246 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q246_cmds as q246_mod
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _get_handlers() -> dict[str, object]:
    """Register commands and return handler dict."""
    q246_mod._state.clear()
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q246_mod.register(reg)
    return {name: cmd.handler for name, cmd in reg._commands.items()}


class TestPromptOptimizeCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["prompt-optimize"]

    def test_add(self):
        result = asyncio.run(self.handler("add Test prompt"))
        self.assertIn("Added variant", result)

    def test_add_no_text(self):
        result = asyncio.run(self.handler("add"))
        self.assertIn("Usage", result)

    def test_score(self):
        r1 = asyncio.run(self.handler("add my prompt"))
        vid = r1.split()[-1]
        result = asyncio.run(self.handler(f"score {vid} 4.5"))
        self.assertIn("Recorded", result)

    def test_score_invalid(self):
        result = asyncio.run(self.handler("score abc"))
        self.assertIn("Usage", result)

    def test_best_empty(self):
        result = asyncio.run(self.handler("best"))
        self.assertIn("No scored", result)

    def test_select_empty(self):
        q246_mod._state.clear()
        handlers = _get_handlers()
        result = asyncio.run(handlers["prompt-optimize"]("select"))
        self.assertIn("No variants", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No variants", result)

    def test_remove_nonexistent(self):
        result = asyncio.run(self.handler("remove xyz"))
        self.assertIn("not found", result)

    def test_stats(self):
        result = asyncio.run(self.handler("stats"))
        self.assertIn("total_variants", result)

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestSystemPromptCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["system-prompt"]

    def test_add_section(self):
        result = asyncio.run(self.handler("add intro Hello World"))
        self.assertIn("Added section", result)

    def test_add_no_content(self):
        result = asyncio.run(self.handler("add intro"))
        self.assertIn("Usage", result)

    def test_remove(self):
        asyncio.run(self.handler("add intro Hello"))
        result = asyncio.run(self.handler("remove intro"))
        self.assertIn("Removed", result)

    def test_remove_not_found(self):
        result = asyncio.run(self.handler("remove nope"))
        self.assertIn("not found", result)

    def test_var(self):
        result = asyncio.run(self.handler("var name Alice"))
        self.assertIn("Set variable", result)

    def test_build(self):
        asyncio.run(self.handler("add intro Hello"))
        result = asyncio.run(self.handler("build"))
        self.assertIn("Hello", result)

    def test_build_empty(self):
        result = asyncio.run(self.handler("build"))
        self.assertIn("empty", result)

    def test_sections(self):
        asyncio.run(self.handler("add intro Hello"))
        result = asyncio.run(self.handler("sections"))
        self.assertIn("intro", result)

    def test_tokens(self):
        asyncio.run(self.handler("add intro Hello"))
        result = asyncio.run(self.handler("tokens"))
        self.assertIn("Estimated", result)

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestFewShotCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["few-shot"]

    def test_add(self):
        result = asyncio.run(self.handler("add What is 2+2? | 4"))
        self.assertIn("Added example", result)

    def test_add_with_tags(self):
        result = asyncio.run(self.handler("add Question | Answer | math,easy"))
        self.assertIn("Added example", result)

    def test_add_no_pipe(self):
        result = asyncio.run(self.handler("add no pipe here"))
        self.assertIn("Usage", result)

    def test_remove_not_found(self):
        result = asyncio.run(self.handler("remove xyz"))
        self.assertIn("not found", result)

    def test_select(self):
        asyncio.run(self.handler("add python func | def foo(): pass"))
        result = asyncio.run(self.handler("select python"))
        self.assertIn("Input:", result)

    def test_select_no_query(self):
        result = asyncio.run(self.handler("select"))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No examples", result)

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestPromptDebugCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["prompt-debug"]

    def test_record(self):
        result = asyncio.run(self.handler("record Hello prompt | Hello response"))
        self.assertIn("Recorded turn", result)

    def test_record_no_pipe(self):
        result = asyncio.run(self.handler("record no pipe"))
        self.assertIn("Usage", result)

    def test_show(self):
        asyncio.run(self.handler("record prompt | response"))
        result = asyncio.run(self.handler("show 0"))
        self.assertIn("prompt", result)

    def test_show_invalid(self):
        result = asyncio.run(self.handler("show abc"))
        self.assertIn("Usage", result)

    def test_diff(self):
        asyncio.run(self.handler("record prompt1 | r1"))
        asyncio.run(self.handler("record prompt2 | r2"))
        result = asyncio.run(self.handler("diff 0 1"))
        self.assertTrue(len(result) > 0)

    def test_tokens(self):
        asyncio.run(self.handler("record prompt | response"))
        result = asyncio.run(self.handler("tokens 0"))
        self.assertIn("prompt_tokens", result)

    def test_history_empty(self):
        result = asyncio.run(self.handler("history"))
        self.assertIn("No turns", result)

    def test_highlight(self):
        asyncio.run(self.handler("record Hello SYSTEM world | response"))
        result = asyncio.run(self.handler("highlight 0 SYSTEM"))
        self.assertIn("[INJECTED: SYSTEM]", result)

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
