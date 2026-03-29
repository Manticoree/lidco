"""Tests for AutomationTriggerRegistry (Task 722)."""
from __future__ import annotations

import json
import unittest

from lidco.scheduler.trigger_registry import (
    AutomationTrigger,
    AutomationTriggerRegistry,
    TriggerAlreadyExistsError,
)


def _make_trigger(name: str = "t1", trigger_type: str = "cron", **kw) -> AutomationTrigger:
    defaults = dict(
        config={},
        instructions_template="Run {{title}}",
        output_type="log",
        memory_key="",
        enabled=True,
    )
    defaults.update(kw)
    return AutomationTrigger(name=name, trigger_type=trigger_type, **defaults)


class TestAutomationTriggerRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = AutomationTriggerRegistry()

    # -- register -----------------------------------------------------------

    def test_register_new_trigger(self):
        t = _make_trigger("a")
        self.reg.register(t)
        self.assertIsNotNone(self.reg.get("a"))

    def test_register_duplicate_raises(self):
        self.reg.register(_make_trigger("a"))
        with self.assertRaises(TriggerAlreadyExistsError):
            self.reg.register(_make_trigger("a"))

    def test_register_duplicate_overwrite(self):
        self.reg.register(_make_trigger("a", output_type="log"))
        self.reg.register(_make_trigger("a", output_type="pr"), overwrite=True)
        self.assertEqual(self.reg.get("a").output_type, "pr")

    def test_register_multiple(self):
        self.reg.register(_make_trigger("a"))
        self.reg.register(_make_trigger("b"))
        self.assertEqual(len(self.reg.list_all()), 2)

    # -- get ----------------------------------------------------------------

    def test_get_existing(self):
        self.reg.register(_make_trigger("x"))
        self.assertEqual(self.reg.get("x").name, "x")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.reg.get("nope"))

    # -- match --------------------------------------------------------------

    def test_match_by_type(self):
        self.reg.register(_make_trigger("c1", "cron"))
        self.reg.register(_make_trigger("g1", "github_pr"))
        matched = self.reg.match("cron")
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].name, "c1")

    def test_match_skips_disabled(self):
        self.reg.register(_make_trigger("c1", "cron"))
        self.reg.disable("c1")
        self.assertEqual(len(self.reg.match("cron")), 0)

    def test_match_returns_all_matching(self):
        self.reg.register(_make_trigger("c1", "cron"))
        self.reg.register(_make_trigger("c2", "cron"))
        self.assertEqual(len(self.reg.match("cron")), 2)

    def test_match_no_matches(self):
        self.reg.register(_make_trigger("c1", "cron"))
        self.assertEqual(len(self.reg.match("slack")), 0)

    def test_match_with_payload_ignored(self):
        self.reg.register(_make_trigger("c1", "webhook"))
        result = self.reg.match("webhook", {"data": 1})
        self.assertEqual(len(result), 1)

    # -- list_all -----------------------------------------------------------

    def test_list_all_empty(self):
        self.assertEqual(self.reg.list_all(), [])

    def test_list_all_returns_copy(self):
        self.reg.register(_make_trigger("a"))
        lst = self.reg.list_all()
        lst.clear()
        self.assertEqual(len(self.reg.list_all()), 1)

    # -- disable / enable ---------------------------------------------------

    def test_disable(self):
        self.reg.register(_make_trigger("d1"))
        self.reg.disable("d1")
        self.assertFalse(self.reg.get("d1").enabled)

    def test_enable(self):
        self.reg.register(_make_trigger("d1", enabled=False))
        self.reg.enable("d1")
        self.assertTrue(self.reg.get("d1").enabled)

    def test_disable_nonexistent_no_error(self):
        self.reg.disable("nope")  # should not raise

    def test_enable_nonexistent_no_error(self):
        self.reg.enable("nope")  # should not raise

    def test_disable_then_enable(self):
        self.reg.register(_make_trigger("d1"))
        self.reg.disable("d1")
        self.assertFalse(self.reg.get("d1").enabled)
        self.reg.enable("d1")
        self.assertTrue(self.reg.get("d1").enabled)

    # -- to_json / from_json ------------------------------------------------

    def test_to_json_empty(self):
        data = json.loads(self.reg.to_json())
        self.assertEqual(data["triggers"], [])

    def test_to_json_roundtrip(self):
        self.reg.register(_make_trigger("r1", "cron", memory_key="mk"))
        serialized = self.reg.to_json()
        reg2 = AutomationTriggerRegistry()
        reg2.from_json(serialized)
        self.assertEqual(reg2.get("r1").name, "r1")
        self.assertEqual(reg2.get("r1").memory_key, "mk")

    def test_from_json_merges(self):
        self.reg.register(_make_trigger("a"))
        data = json.dumps({"triggers": [{"name": "b", "trigger_type": "slack", "instructions_template": "t", "output_type": "log"}]})
        self.reg.from_json(data)
        self.assertIsNotNone(self.reg.get("a"))
        self.assertIsNotNone(self.reg.get("b"))

    def test_from_json_overwrites_existing(self):
        self.reg.register(_make_trigger("a", output_type="log"))
        data = json.dumps({"triggers": [{"name": "a", "trigger_type": "cron", "instructions_template": "t", "output_type": "pr"}]})
        self.reg.from_json(data)
        self.assertEqual(self.reg.get("a").output_type, "pr")

    def test_from_json_empty_triggers(self):
        self.reg.from_json('{"triggers": []}')
        self.assertEqual(self.reg.list_all(), [])

    # -- dataclass fields ---------------------------------------------------

    def test_trigger_defaults(self):
        t = AutomationTrigger(name="t", trigger_type="cron", config={}, instructions_template="x", output_type="log")
        self.assertEqual(t.memory_key, "")
        self.assertTrue(t.enabled)

    def test_trigger_custom_memory_key(self):
        t = _make_trigger("t", memory_key="my_key")
        self.assertEqual(t.memory_key, "my_key")

    def test_trigger_equality(self):
        t1 = _make_trigger("t")
        t2 = _make_trigger("t")
        self.assertEqual(t1, t2)


if __name__ == "__main__":
    unittest.main()
