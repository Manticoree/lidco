"""Tests for lidco.cron.triggers."""

from __future__ import annotations

import pytest

from lidco.cron.triggers import CompoundTrigger, Trigger, TriggerRegistry, TriggerType


@pytest.fixture
def registry() -> TriggerRegistry:
    return TriggerRegistry()


class TestTriggerRegistry:
    def test_add_and_get(self, registry: TriggerRegistry) -> None:
        t = Trigger(name="t1", trigger_type=TriggerType.MANUAL)
        registry.add(t)
        assert registry.get("t1") is not None
        assert registry.get("t1").name == "t1"  # type: ignore[union-attr]

    def test_remove(self, registry: TriggerRegistry) -> None:
        t = Trigger(name="t1", trigger_type=TriggerType.MANUAL)
        registry.add(t)
        assert registry.remove("t1")
        assert registry.get("t1") is None

    def test_remove_nonexistent(self, registry: TriggerRegistry) -> None:
        assert not registry.remove("nope")

    def test_list_triggers(self, registry: TriggerRegistry) -> None:
        registry.add(Trigger(name="a", trigger_type=TriggerType.MANUAL))
        registry.add(Trigger(name="b", trigger_type=TriggerType.TIME))
        assert len(registry.list_triggers()) == 2

    def test_evaluate_file_change(self, registry: TriggerRegistry) -> None:
        t = Trigger(
            name="fc",
            trigger_type=TriggerType.FILE_CHANGE,
            config={"pattern": ".py"},
        )
        registry.add(t)
        assert registry.evaluate("fc", {"changed_files": ["main.py"]})
        assert not registry.evaluate("fc", {"changed_files": ["data.csv"]})

    def test_evaluate_file_change_no_pattern(self, registry: TriggerRegistry) -> None:
        t = Trigger(name="fc2", trigger_type=TriggerType.FILE_CHANGE)
        registry.add(t)
        assert registry.evaluate("fc2", {"changed_files": ["a.txt"]})
        assert not registry.evaluate("fc2", {"changed_files": []})

    def test_evaluate_time_trigger(self, registry: TriggerRegistry) -> None:
        t = Trigger(name="tm", trigger_type=TriggerType.TIME)
        registry.add(t)
        assert registry.evaluate("tm", {"time_match": True})
        assert not registry.evaluate("tm", {"time_match": False})

    def test_evaluate_disabled(self, registry: TriggerRegistry) -> None:
        t = Trigger(name="d", trigger_type=TriggerType.MANUAL, enabled=False)
        registry.add(t)
        assert not registry.evaluate("d", {"manual": True})

    def test_compound_and(self, registry: TriggerRegistry) -> None:
        t1 = Trigger(name="a", trigger_type=TriggerType.MANUAL)
        t2 = Trigger(name="b", trigger_type=TriggerType.TIME)
        compound = CompoundTrigger(name="both", operator="AND", triggers=(t1, t2))
        registry.add_compound(compound)
        assert registry.evaluate_compound("both", {"manual": True, "time_match": True})
        assert not registry.evaluate_compound(
            "both", {"manual": True, "time_match": False}
        )

    def test_compound_or(self, registry: TriggerRegistry) -> None:
        t1 = Trigger(name="a", trigger_type=TriggerType.MANUAL)
        t2 = Trigger(name="b", trigger_type=TriggerType.TIME)
        compound = CompoundTrigger(name="either", operator="OR", triggers=(t1, t2))
        registry.add_compound(compound)
        assert registry.evaluate_compound(
            "either", {"manual": False, "time_match": True}
        )
        assert not registry.evaluate_compound(
            "either", {"manual": False, "time_match": False}
        )

    def test_compound_disabled(self, registry: TriggerRegistry) -> None:
        compound = CompoundTrigger(
            name="off",
            operator="AND",
            triggers=(Trigger(name="a", trigger_type=TriggerType.MANUAL),),
            enabled=False,
        )
        registry.add_compound(compound)
        assert not registry.evaluate_compound("off", {"manual": True})
