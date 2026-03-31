"""Tests for PasteMode."""
from __future__ import annotations

import unittest

from lidco.bridge.paste_mode import PasteMode


class TestFormatForWeb(unittest.TestCase):
    def setUp(self):
        self.pm = PasteMode()

    def test_includes_context_header(self):
        result = self.pm.format_for_web("some context", "what is this?")
        self.assertIn("Context:", result)
        self.assertIn("some context", result)

    def test_includes_question_header(self):
        result = self.pm.format_for_web("ctx", "my question")
        self.assertIn("Question:", result)
        self.assertIn("my question", result)

    def test_empty_context_omitted(self):
        result = self.pm.format_for_web("", "question only")
        self.assertNotIn("Context:", result)
        self.assertIn("Question:", result)

    def test_whitespace_context_omitted(self):
        result = self.pm.format_for_web("   ", "q")
        self.assertNotIn("Context:", result)


class TestParseResponse(unittest.TestCase):
    def setUp(self):
        self.pm = PasteMode()

    def test_no_code_blocks(self):
        parsed = self.pm.parse_response("Just plain text response.")
        self.assertEqual(parsed["text"], "Just plain text response.")
        self.assertEqual(parsed["code_blocks"], [])
        self.assertFalse(parsed["has_code"])

    def test_single_code_block(self):
        raw = "Here is code:\n```python\ndef foo():\n    pass\n```\nDone."
        parsed = self.pm.parse_response(raw)
        self.assertEqual(len(parsed["code_blocks"]), 1)
        self.assertIn("def foo():", parsed["code_blocks"][0])
        self.assertTrue(parsed["has_code"])

    def test_multiple_code_blocks(self):
        raw = "```\nblock1\n```\ntext\n```js\nblock2\n```"
        parsed = self.pm.parse_response(raw)
        self.assertEqual(len(parsed["code_blocks"]), 2)

    def test_text_excludes_code_fences(self):
        raw = "Before\n```\ncode\n```\nAfter"
        parsed = self.pm.parse_response(raw)
        self.assertNotIn("```", parsed["text"])
        self.assertIn("Before", parsed["text"])
        self.assertIn("After", parsed["text"])


class TestRoundtrip(unittest.TestCase):
    def setUp(self):
        self.pm = PasteMode()

    def test_roundtrip_structure(self):
        result = self.pm.roundtrip("ctx", "q?", "Answer here\n```\ncode\n```")
        self.assertIn("prompt", result)
        self.assertIn("context", result)
        self.assertIn("question", result)
        self.assertIn("response", result)

    def test_roundtrip_context_preserved(self):
        result = self.pm.roundtrip("my context", "my question", "response")
        self.assertEqual(result["context"], "my context")
        self.assertEqual(result["question"], "my question")

    def test_roundtrip_response_parsed(self):
        result = self.pm.roundtrip("c", "q", "```\nsome code\n```")
        self.assertTrue(result["response"]["has_code"])

    def test_roundtrip_prompt_formatted(self):
        result = self.pm.roundtrip("c", "q", "r")
        self.assertIn("Context:", result["prompt"])
        self.assertIn("Question:", result["prompt"])


if __name__ == "__main__":
    unittest.main()
