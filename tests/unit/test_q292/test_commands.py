"""Tests for CommandBridge."""
import unittest

from lidco.slack.commands import CommandBridge


class TestCommandBridge(unittest.TestCase):

    def test_parse_mention_valid(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("@lidco status")
        self.assertEqual(cmd, "status")
        self.assertEqual(args, "")

    def test_parse_mention_with_args(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("@lidco deploy staging")
        self.assertEqual(cmd, "deploy")
        self.assertEqual(args, "staging")

    def test_parse_mention_case_insensitive(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("@LIDCO help")
        self.assertEqual(cmd, "help")

    def test_parse_mention_no_prefix(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("hello there")
        self.assertEqual(cmd, "")
        self.assertEqual(args, "")

    def test_parse_mention_empty_string(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("")
        self.assertEqual(cmd, "")

    def test_parse_mention_only_prefix(self):
        cb = CommandBridge()
        cmd, args = cb.parse_mention("@lidco")
        self.assertEqual(cmd, "help")

    def test_execute_registered_handler(self):
        cb = CommandBridge()
        cb.register_handler("ping", lambda a: "pong")
        result = cb.execute("@lidco ping")
        self.assertEqual(result, "pong")

    def test_execute_unknown_command(self):
        cb = CommandBridge()
        result = cb.execute("@lidco unknown_xyz")
        self.assertIn("Unknown command", result)

    def test_execute_invalid_mention(self):
        cb = CommandBridge()
        result = cb.execute("not a mention")
        self.assertIn("Error", result)

    def test_register_empty_cmd_raises(self):
        cb = CommandBridge()
        with self.assertRaises(ValueError):
            cb.register_handler("", lambda a: "x")

    def test_register_none_handler_raises(self):
        cb = CommandBridge()
        with self.assertRaises(ValueError):
            cb.register_handler("test", None)  # type: ignore[arg-type]

    def test_list_commands_sorted(self):
        cb = CommandBridge()
        cb.register_handler("zebra", lambda a: "z")
        cb.register_handler("alpha", lambda a: "a")
        self.assertEqual(cb.list_commands(), ["alpha", "zebra"])

    def test_default_handler_fallback(self):
        cb = CommandBridge()
        cb.set_default_handler(lambda text: f"default: {text}")
        result = cb.execute("@lidco mystery arg1")
        self.assertEqual(result, "default: mystery arg1")

    def test_execute_handler_exception(self):
        cb = CommandBridge()
        cb.register_handler("fail", lambda a: 1 / 0)
        result = cb.execute("@lidco fail")
        self.assertIn("Error executing", result)


if __name__ == "__main__":
    unittest.main()
