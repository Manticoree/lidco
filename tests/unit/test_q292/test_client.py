"""Tests for SlackClient."""
import unittest

from lidco.slack.client import SlackClient, RateLimitInfo


class TestSlackClient(unittest.TestCase):

    def test_send_message_returns_dict(self):
        c = SlackClient(token="xoxb-test")
        result = c.send_message("general", "hello")
        self.assertTrue(result["ok"])
        self.assertEqual(result["channel"], "general")
        self.assertEqual(result["text"], "hello")
        self.assertIn("ts", result)
        self.assertIn("message_id", result)

    def test_send_message_empty_channel_raises(self):
        c = SlackClient()
        with self.assertRaises(ValueError):
            c.send_message("", "hello")

    def test_send_message_empty_text_raises(self):
        c = SlackClient()
        with self.assertRaises(ValueError):
            c.send_message("general", "")

    def test_list_channels_returns_defaults(self):
        c = SlackClient()
        channels = c.list_channels()
        self.assertIsInstance(channels, list)
        self.assertEqual(len(channels), 3)
        names = [ch["name"] for ch in channels]
        self.assertIn("general", names)

    def test_get_thread_returns_matching_messages(self):
        c = SlackClient()
        r = c.send_message("dev", "thread msg")
        ts = r["ts"]
        thread = c.get_thread("dev", ts)
        self.assertEqual(len(thread), 1)
        self.assertEqual(thread[0]["text"], "thread msg")

    def test_get_thread_empty_channel_raises(self):
        c = SlackClient()
        with self.assertRaises(ValueError):
            c.get_thread("", "123")

    def test_upload_file_returns_metadata(self):
        c = SlackClient()
        result = c.upload_file("general", "file content", "test.py")
        self.assertTrue(result["ok"])
        self.assertEqual(result["channel"], "general")
        self.assertEqual(result["filename"], "test.py")
        self.assertEqual(result["size"], len("file content"))

    def test_upload_file_empty_filename_raises(self):
        c = SlackClient()
        with self.assertRaises(ValueError):
            c.upload_file("general", "content", "")

    def test_rate_limit_info(self):
        c = SlackClient(rate_limit=10)
        c.send_message("general", "hi")
        info = c.rate_limit_info()
        self.assertIsInstance(info, RateLimitInfo)
        self.assertEqual(info.calls_made, 1)
        self.assertEqual(info.max_calls, 10)
        self.assertEqual(info.remaining, 9)

    def test_rate_limit_exceeded(self):
        c = SlackClient(rate_limit=2)
        c.send_message("general", "1")
        c.send_message("general", "2")
        with self.assertRaises(RuntimeError):
            c.send_message("general", "3")

    def test_token_type_check(self):
        with self.assertRaises(TypeError):
            SlackClient(token=123)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
