"""Tests for lidco.response.parser."""
from __future__ import annotations

import unittest

from lidco.response.parser import ParsedResponse, ResponseParser


class TestResponseParser(unittest.TestCase):
    """Tests for ResponseParser."""

    def setUp(self) -> None:
        self.parser = ResponseParser()

    # -- ParsedResponse dataclass ------------------------------------------

    def test_parsed_response_defaults(self) -> None:
        pr = ParsedResponse()
        self.assertEqual(pr.text_blocks, [])
        self.assertEqual(pr.code_blocks, [])
        self.assertEqual(pr.tool_calls, [])
        self.assertEqual(pr.thinking, "")

    def test_parsed_response_frozen(self) -> None:
        pr = ParsedResponse()
        with self.assertRaises(AttributeError):
            pr.thinking = "oops"  # type: ignore[misc]

    # -- extract_code_blocks -----------------------------------------------

    def test_extract_code_blocks_none(self) -> None:
        self.assertEqual(self.parser.extract_code_blocks("no code here"), [])

    def test_extract_code_blocks_single(self) -> None:
        text = "Here:\n```python\nprint('hi')\n```\nDone."
        blocks = self.parser.extract_code_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["language"], "python")
        self.assertIn("print", blocks[0]["code"])

    def test_extract_code_blocks_multiple(self) -> None:
        text = "```js\nalert(1)\n```\n```rust\nfn main(){}\n```"
        blocks = self.parser.extract_code_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["language"], "js")
        self.assertEqual(blocks[1]["language"], "rust")

    def test_extract_code_blocks_no_lang(self) -> None:
        text = "```\nplain code\n```"
        blocks = self.parser.extract_code_blocks(text)
        self.assertEqual(blocks[0]["language"], "text")

    # -- extract_tool_calls ------------------------------------------------

    def test_extract_tool_calls_none(self) -> None:
        self.assertEqual(self.parser.extract_tool_calls("no tools"), [])

    def test_extract_tool_calls_single(self) -> None:
        text = "<tool_use>\n<name>read_file</name>\n<input>path.py</input>\n</tool_use>"
        calls = self.parser.extract_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "read_file")
        self.assertEqual(calls[0]["input"], "path.py")

    def test_extract_tool_calls_multiple(self) -> None:
        text = (
            "<tool_use><name>a</name><input>1</input></tool_use>"
            "<tool_use><name>b</name><input>2</input></tool_use>"
        )
        calls = self.parser.extract_tool_calls(text)
        self.assertEqual(len(calls), 2)

    # -- separate_thinking -------------------------------------------------

    def test_separate_thinking_no_tags(self) -> None:
        thinking, output = self.parser.separate_thinking("hello world")
        self.assertEqual(thinking, "")
        self.assertEqual(output, "hello world")

    def test_separate_thinking_with_tags(self) -> None:
        text = "<thinking>Let me think...</thinking>Answer here."
        thinking, output = self.parser.separate_thinking(text)
        self.assertEqual(thinking, "Let me think...")
        self.assertEqual(output, "Answer here.")

    # -- parse -------------------------------------------------------------

    def test_parse_plain_text(self) -> None:
        pr = self.parser.parse("Just some text.")
        self.assertGreater(len(pr.text_blocks), 0)
        self.assertEqual(pr.code_blocks, [])
        self.assertEqual(pr.tool_calls, [])
        self.assertEqual(pr.thinking, "")

    def test_parse_mixed(self) -> None:
        text = (
            "<thinking>hmm</thinking>"
            "Hello\n\n```python\nx=1\n```\n\n"
            "<tool_use><name>t</name><input>i</input></tool_use>"
        )
        pr = self.parser.parse(text)
        self.assertEqual(pr.thinking, "hmm")
        self.assertEqual(len(pr.code_blocks), 1)
        self.assertEqual(len(pr.tool_calls), 1)

    def test_parse_empty(self) -> None:
        pr = self.parser.parse("")
        self.assertEqual(pr.text_blocks, [])
        self.assertEqual(pr.code_blocks, [])

    def test_parse_only_code(self) -> None:
        text = "```python\npass\n```"
        pr = self.parser.parse(text)
        self.assertEqual(len(pr.code_blocks), 1)

    def test_parse_preserves_code_content(self) -> None:
        code = "def foo():\n    return 42\n"
        text = f"```python\n{code}```"
        pr = self.parser.parse(text)
        self.assertEqual(pr.code_blocks[0]["code"], code)


if __name__ == "__main__":
    unittest.main()
