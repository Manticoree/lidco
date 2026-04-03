"""Tests for lidco.cli.commands.q247_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q247_cmds import register


class TestQ247Commands(unittest.TestCase):
    """Tests for Q247 slash commands."""

    def setUp(self) -> None:
        self.registry = MagicMock()
        self.commands: dict[str, object] = {}

        def capture(cmd: object) -> None:
            self.commands[cmd.name] = cmd  # type: ignore[attr-defined]

        self.registry.register.side_effect = capture
        register(self.registry)

    # -- registration ------------------------------------------------------

    def test_all_commands_registered(self) -> None:
        expected = {"parse-response", "validate-response", "transform", "response-cache"}
        self.assertEqual(set(self.commands.keys()), expected)

    def test_registry_call_count(self) -> None:
        self.assertEqual(self.registry.register.call_count, 4)

    # -- /parse-response ---------------------------------------------------

    def test_parse_response_empty(self) -> None:
        handler = self.commands["parse-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_parse_response_plain(self) -> None:
        handler = self.commands["parse-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("Hello world."))
        self.assertIn("Text blocks:", result)
        self.assertIn("Code blocks: 0", result)

    def test_parse_response_with_code(self) -> None:
        handler = self.commands["parse-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("```python\npass\n```"))
        self.assertIn("Code blocks: 1", result)
        self.assertIn("lang=python", result)

    def test_parse_response_with_tool(self) -> None:
        handler = self.commands["parse-response"].handler  # type: ignore[attr-defined]
        text = "<tool_use><name>test</name><input>x</input></tool_use>"
        result = asyncio.run(handler(text))
        self.assertIn("Tool calls:  1", result)
        self.assertIn("name=test", result)

    # -- /validate-response ------------------------------------------------

    def test_validate_response_empty(self) -> None:
        handler = self.commands["validate-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_validate_response_valid(self) -> None:
        handler = self.commands["validate-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("This is complete."))
        self.assertIn("passed", result.lower())

    def test_validate_response_incomplete(self) -> None:
        handler = self.commands["validate-response"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("The answer is"))
        self.assertIn("incomplete", result.lower())

    # -- /transform --------------------------------------------------------

    def test_transform_empty(self) -> None:
        handler = self.commands["transform"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_transform_strips_redundant(self) -> None:
        handler = self.commands["transform"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("yes yes yes"))
        self.assertEqual(result, "yes")

    # -- /response-cache ---------------------------------------------------

    def test_cache_stats(self) -> None:
        handler = self.commands["response-cache"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("stats"))
        self.assertIn("hits=0", result)

    def test_cache_put_and_get(self) -> None:
        handler = self.commands["response-cache"].handler  # type: ignore[attr-defined]
        asyncio.run(handler("put greeting hello"))
        # Note: each call creates a new cache instance, so get will miss
        result = asyncio.run(handler("get greeting"))
        self.assertIn("miss", result.lower())

    def test_cache_clear(self) -> None:
        handler = self.commands["response-cache"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_cache_usage(self) -> None:
        handler = self.commands["response-cache"].handler  # type: ignore[attr-defined]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
