"""Tests for CodeShare."""
import unittest

from lidco.slack.client import SlackClient
from lidco.slack.code_share import CodeShare, SharedSnippet


class TestCodeShare(unittest.TestCase):

    def _make(self):
        return CodeShare(SlackClient())

    def test_share_returns_dict(self):
        cs = self._make()
        result = cs.share("print('hi')", "python", "dev")
        self.assertTrue(result["ok"])
        self.assertEqual(result["channel"], "dev")
        self.assertEqual(result["language"], "python")
        self.assertIn("snippet_id", result)

    def test_share_empty_code_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.share("", "python", "dev")

    def test_share_empty_channel_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.share("code", "python", "")

    def test_share_empty_language_defaults_to_text(self):
        cs = self._make()
        result = cs.share("code", "", "dev")
        self.assertEqual(result["language"], "text")

    def test_create_thread_returns_string(self):
        cs = self._make()
        thread_id = cs.create_thread("dev", "Discussion topic")
        self.assertIsInstance(thread_id, str)
        self.assertTrue(len(thread_id) > 0)

    def test_create_thread_empty_channel_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.create_thread("", "title")

    def test_create_thread_empty_title_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.create_thread("dev", "")

    def test_attach_file_returns_metadata(self):
        cs = self._make()
        thread_id = cs.create_thread("dev", "Topic")
        result = cs.attach_file(thread_id, "file content", "data.txt")
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "data.txt")
        self.assertEqual(result["thread"], thread_id)

    def test_attach_file_empty_thread_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.attach_file("", "content", "file.txt")

    def test_attach_file_empty_name_raises(self):
        cs = self._make()
        with self.assertRaises(ValueError):
            cs.attach_file("thread1", "content", "")

    def test_list_snippets(self):
        cs = self._make()
        cs.share("code1", "python", "dev")
        cs.share("code2", "js", "general")
        snippets = cs.list_snippets()
        self.assertEqual(len(snippets), 2)
        self.assertIsInstance(snippets[0], SharedSnippet)


if __name__ == "__main__":
    unittest.main()
