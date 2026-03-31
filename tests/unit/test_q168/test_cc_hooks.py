"""Tests for cc_hooks (Task 955)."""
from __future__ import annotations

import unittest

from lidco.compat.cc_hooks import CCHook, parse_cc_hooks, to_lidco_hooks


class TestCCHook(unittest.TestCase):
    def test_defaults(self):
        h = CCHook()
        self.assertEqual(h.event, "")
        self.assertEqual(h.command, "")
        self.assertIsNone(h.matcher)
        self.assertEqual(h.timeout, 30)


class TestParseCCHooks(unittest.TestCase):
    def test_parse_dict_hooks(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"command": "echo pre", "matcher": "Bash", "timeout": 10},
                ],
                "PostToolUse": [
                    {"command": "prettier --write $FILE"},
                ],
            }
        }
        hooks = parse_cc_hooks(settings)
        self.assertEqual(len(hooks), 2)
        pre = [h for h in hooks if h.event == "PreToolUse"]
        self.assertEqual(len(pre), 1)
        self.assertEqual(pre[0].command, "echo pre")
        self.assertEqual(pre[0].matcher, "Bash")
        self.assertEqual(pre[0].timeout, 10)

    def test_parse_string_hooks(self):
        settings = {
            "hooks": {
                "Stop": ["echo goodbye"],
            }
        }
        hooks = parse_cc_hooks(settings)
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0].event, "Stop")
        self.assertEqual(hooks[0].command, "echo goodbye")
        self.assertIsNone(hooks[0].matcher)

    def test_parse_direct_hooks_section(self):
        """Accept hooks dict directly (no wrapping 'hooks' key)."""
        hooks_section = {
            "PreToolUse": [{"command": "cmd1"}],
        }
        hooks = parse_cc_hooks(hooks_section)
        self.assertEqual(len(hooks), 1)

    def test_parse_empty(self):
        self.assertEqual(parse_cc_hooks({"hooks": {}}), [])

    def test_parse_no_hooks_key(self):
        self.assertEqual(parse_cc_hooks({}), [])

    def test_parse_non_list_value_skipped(self):
        hooks = parse_cc_hooks({"hooks": {"PreToolUse": "not-a-list"}})
        self.assertEqual(len(hooks), 0)

    def test_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            parse_cc_hooks("bad")  # type: ignore[arg-type]

    def test_matcher_none_when_empty(self):
        hooks = parse_cc_hooks({"hooks": {"Stop": [{"command": "x", "matcher": ""}]}})
        self.assertIsNone(hooks[0].matcher)

    def test_default_timeout(self):
        hooks = parse_cc_hooks({"hooks": {"Stop": [{"command": "x"}]}})
        self.assertEqual(hooks[0].timeout, 30)

    def test_notification_event(self):
        hooks = parse_cc_hooks({"hooks": {"Notification": [{"command": "notify"}]}})
        self.assertEqual(hooks[0].event, "Notification")


class TestToLidcoHooks(unittest.TestCase):
    def test_event_mapping(self):
        hooks = [
            CCHook(event="PreToolUse", command="cmd1"),
            CCHook(event="PostToolUse", command="cmd2"),
            CCHook(event="Stop", command="cmd3"),
            CCHook(event="Notification", command="cmd4"),
        ]
        result = to_lidco_hooks(hooks)
        events = [r["event"] for r in result]
        self.assertEqual(events, ["pre_tool_use", "post_tool_use", "session_end", "notification"])

    def test_command_preserved(self):
        hooks = [CCHook(event="Stop", command="echo done")]
        result = to_lidco_hooks(hooks)
        self.assertEqual(result[0]["command"], "echo done")

    def test_matcher_included_when_set(self):
        hooks = [CCHook(event="PreToolUse", command="x", matcher="Bash")]
        result = to_lidco_hooks(hooks)
        self.assertEqual(result[0]["matcher"], "Bash")

    def test_matcher_omitted_when_none(self):
        hooks = [CCHook(event="Stop", command="x")]
        result = to_lidco_hooks(hooks)
        self.assertNotIn("matcher", result[0])

    def test_timeout_included_when_non_default(self):
        hooks = [CCHook(event="Stop", command="x", timeout=60)]
        result = to_lidco_hooks(hooks)
        self.assertEqual(result[0]["timeout"], 60)

    def test_timeout_omitted_when_default(self):
        hooks = [CCHook(event="Stop", command="x", timeout=30)]
        result = to_lidco_hooks(hooks)
        self.assertNotIn("timeout", result[0])

    def test_empty_list(self):
        self.assertEqual(to_lidco_hooks([]), [])

    def test_unknown_event_lowercased(self):
        hooks = [CCHook(event="CustomEvent", command="x")]
        result = to_lidco_hooks(hooks)
        self.assertEqual(result[0]["event"], "customevent")
