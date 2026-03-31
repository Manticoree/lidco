"""Tests for PromptRewriter — Q176."""
from __future__ import annotations

import unittest

from lidco.input.prompt_rewriter import PromptRewriter, RewriteResult


class TestPromptRewriter(unittest.TestCase):
    def setUp(self):
        self.rewriter = PromptRewriter()

    # --- Specific prompts (no rewrite) ---
    def test_specific_prompt_unchanged(self):
        result = self.rewriter.rewrite("add a login endpoint to auth.py")
        self.assertFalse(result.was_rewritten)
        self.assertEqual(result.rewritten, "add a login endpoint to auth.py")

    def test_detailed_prompt_unchanged(self):
        result = self.rewriter.rewrite("refactor the database layer to use connection pooling")
        self.assertFalse(result.was_rewritten)

    def test_code_prompt_unchanged(self):
        result = self.rewriter.rewrite("def hello(): return 'world'")
        self.assertFalse(result.was_rewritten)

    # --- Vague prompts without context ---
    def test_fix_it_no_context(self):
        result = self.rewriter.rewrite("fix it")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Fix", result.rewritten)

    def test_do_it_no_context(self):
        result = self.rewriter.rewrite("do it")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Continue", result.rewritten)

    def test_make_it_work_no_context(self):
        result = self.rewriter.rewrite("make it work")
        self.assertTrue(result.was_rewritten)

    def test_try_again_no_context(self):
        result = self.rewriter.rewrite("try again")
        self.assertTrue(result.was_rewritten)

    def test_yes_no_context(self):
        result = self.rewriter.rewrite("yes")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Continue", result.rewritten)

    def test_no_prompt(self):
        result = self.rewriter.rewrite("no")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Cancel", result.rewritten)

    def test_help_no_context(self):
        result = self.rewriter.rewrite("help")
        self.assertTrue(result.was_rewritten)

    def test_continue_no_context(self):
        result = self.rewriter.rewrite("continue")
        self.assertTrue(result.was_rewritten)

    # --- Vague prompts WITH context ---
    def test_fix_it_with_last_error(self):
        result = self.rewriter.rewrite("fix it", {"last_error": "NameError: x is not defined"})
        self.assertTrue(result.was_rewritten)
        self.assertIn("NameError", result.rewritten)
        self.assertIn("added_last_error", result.expansions)

    def test_fix_it_with_current_file(self):
        result = self.rewriter.rewrite("fix it", {"current_file": "src/auth.py"})
        self.assertTrue(result.was_rewritten)
        self.assertIn("src/auth.py", result.rewritten)

    def test_do_it_with_current_file(self):
        result = self.rewriter.rewrite("do it", {"current_file": "main.py"})
        self.assertIn("main.py", result.rewritten)

    def test_help_with_last_error(self):
        result = self.rewriter.rewrite("help", {"last_error": "ImportError"})
        self.assertIn("ImportError", result.rewritten)

    def test_help_with_current_file(self):
        result = self.rewriter.rewrite("help", {"current_file": "app.py"})
        self.assertIn("app.py", result.rewritten)

    def test_recent_files_appended(self):
        result = self.rewriter.rewrite("fix it", {"recent_files": "a.py, b.py"})
        self.assertIn("recently edited", result.rewritten)
        self.assertIn("added_recent_files", result.expansions)

    # --- Edge cases ---
    def test_empty_string(self):
        result = self.rewriter.rewrite("")
        self.assertFalse(result.was_rewritten)
        self.assertEqual(result.rewritten, "")

    def test_whitespace_only(self):
        result = self.rewriter.rewrite("   ")
        self.assertFalse(result.was_rewritten)

    def test_result_is_frozen(self):
        result = self.rewriter.rewrite("fix it")
        with self.assertRaises(AttributeError):
            result.was_rewritten = False  # type: ignore[misc]

    def test_original_preserved(self):
        result = self.rewriter.rewrite("fix it")
        self.assertEqual(result.original, "fix it")

    def test_again_prompt(self):
        result = self.rewriter.rewrite("again")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Repeat", result.rewritten)

    def test_same_thing(self):
        result = self.rewriter.rewrite("same thing")
        self.assertTrue(result.was_rewritten)
        self.assertIn("Repeat", result.rewritten)

    def test_go_ahead(self):
        result = self.rewriter.rewrite("go ahead")
        self.assertTrue(result.was_rewritten)

    def test_what_now(self):
        result = self.rewriter.rewrite("what now?")
        self.assertTrue(result.was_rewritten)


if __name__ == "__main__":
    unittest.main()
