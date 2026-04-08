"""Tests for lidco.sre.oncall — On-Call Manager."""
from __future__ import annotations

import time
import unittest

from lidco.sre.oncall import (
    EscalationLevel,
    EscalationPolicy,
    FatigueRecord,
    HandoffNote,
    OnCallError,
    OnCallManager,
    OnCallPerson,
    Override,
    RotationSlot,
)


class TestOnCallDataclasses(unittest.TestCase):
    def test_oncall_person_defaults(self) -> None:
        p = OnCallPerson(name="Alice")
        self.assertEqual(p.name, "Alice")
        self.assertTrue(len(p.id) > 0)

    def test_rotation_slot_is_active(self) -> None:
        now = time.time()
        slot = RotationSlot(person_id="x", start_epoch=now - 100, end_epoch=now + 100)
        self.assertTrue(slot.is_active())

    def test_rotation_slot_not_active(self) -> None:
        now = time.time()
        slot = RotationSlot(person_id="x", start_epoch=now + 100, end_epoch=now + 200)
        self.assertFalse(slot.is_active())

    def test_rotation_slot_duration_hours(self) -> None:
        slot = RotationSlot(person_id="x", start_epoch=0, end_epoch=7200)
        self.assertAlmostEqual(slot.duration_hours(), 2.0)

    def test_override_is_active(self) -> None:
        now = time.time()
        ov = Override(start_epoch=now - 10, end_epoch=now + 10)
        self.assertTrue(ov.is_active())
        ov2 = Override(start_epoch=now + 100, end_epoch=now + 200)
        self.assertFalse(ov2.is_active())

    def test_escalation_policy_defaults(self) -> None:
        pol = EscalationPolicy(name="default")
        self.assertEqual(len(pol.levels), 3)
        self.assertEqual(pol.timeout_seconds, 300.0)

    def test_fatigue_record_score_zero(self) -> None:
        fr = FatigueRecord(person_id="x")
        self.assertAlmostEqual(fr.fatigue_score(), 0.0)

    def test_fatigue_record_score_max(self) -> None:
        fr = FatigueRecord(person_id="x", hours_on_call=200, incidents_handled=20, pages_received=30)
        score = fr.fatigue_score()
        self.assertGreater(score, 90)
        self.assertLessEqual(score, 100)

    def test_handoff_note(self) -> None:
        note = HandoffNote(from_person_id="a", to_person_id="b", content="All clear", open_issues=["ticket-1"])
        self.assertEqual(len(note.open_issues), 1)

    def test_escalation_level_values(self) -> None:
        self.assertEqual(EscalationLevel.PRIMARY.value, "primary")
        self.assertEqual(EscalationLevel.EXECUTIVE.value, "executive")


class TestOnCallManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = OnCallManager()

    def _add_person(self, name: str = "Alice", email: str = "alice@test.com") -> OnCallPerson:
        return self.mgr.add_person(OnCallPerson(name=name, email=email))

    def test_add_person(self) -> None:
        p = self._add_person()
        self.assertEqual(p.name, "Alice")
        self.assertEqual(len(self.mgr.list_people()), 1)

    def test_add_person_no_name_raises(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.add_person(OnCallPerson(name=""))

    def test_get_person(self) -> None:
        p = self._add_person()
        result = self.mgr.get_person(p.id)
        self.assertEqual(result.name, "Alice")

    def test_get_person_not_found(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.get_person("nope")

    def test_add_slot(self) -> None:
        p = self._add_person()
        now = time.time()
        slot = self.mgr.add_slot(RotationSlot(person_id=p.id, start_epoch=now, end_epoch=now + 3600))
        self.assertEqual(len(self.mgr.list_slots()), 1)

    def test_add_slot_bad_person(self) -> None:
        now = time.time()
        with self.assertRaises(OnCallError):
            self.mgr.add_slot(RotationSlot(person_id="bad", start_epoch=now, end_epoch=now + 1))

    def test_add_slot_bad_times(self) -> None:
        p = self._add_person()
        now = time.time()
        with self.assertRaises(OnCallError):
            self.mgr.add_slot(RotationSlot(person_id=p.id, start_epoch=now, end_epoch=now))

    def test_current_on_call(self) -> None:
        p = self._add_person()
        now = time.time()
        self.mgr.add_slot(RotationSlot(person_id=p.id, start_epoch=now - 100, end_epoch=now + 100))
        result = self.mgr.current_on_call()
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Alice")

    def test_current_on_call_none(self) -> None:
        self.assertIsNone(self.mgr.current_on_call())

    def test_current_on_call_with_override(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        now = time.time()
        self.mgr.add_slot(RotationSlot(person_id=alice.id, start_epoch=now - 100, end_epoch=now + 100))
        self.mgr.add_override(Override(
            original_person_id=alice.id,
            replacement_person_id=bob.id,
            start_epoch=now - 50,
            end_epoch=now + 50,
        ))
        result = self.mgr.current_on_call()
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Bob")

    def test_list_slots_by_person(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        now = time.time()
        self.mgr.add_slot(RotationSlot(person_id=alice.id, start_epoch=now, end_epoch=now + 1))
        self.mgr.add_slot(RotationSlot(person_id=bob.id, start_epoch=now, end_epoch=now + 1))
        self.assertEqual(len(self.mgr.list_slots(alice.id)), 1)

    def test_add_override(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        now = time.time()
        ov = self.mgr.add_override(Override(
            original_person_id=alice.id,
            replacement_person_id=bob.id,
            start_epoch=now, end_epoch=now + 3600,
        ))
        self.assertEqual(len(self.mgr.list_overrides()), 1)

    def test_add_override_bad_replacement(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.add_override(Override(replacement_person_id="bad"))

    def test_list_overrides_active_only(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        now = time.time()
        self.mgr.add_override(Override(
            replacement_person_id=bob.id, start_epoch=now - 10, end_epoch=now + 10,
        ))
        self.mgr.add_override(Override(
            replacement_person_id=alice.id, start_epoch=now + 1000, end_epoch=now + 2000,
        ))
        active = self.mgr.list_overrides(active_only=True)
        self.assertEqual(len(active), 1)

    def test_add_policy(self) -> None:
        pol = self.mgr.add_policy(EscalationPolicy(name="default"))
        self.assertEqual(pol.name, "default")

    def test_add_policy_no_name_raises(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.add_policy(EscalationPolicy(name=""))

    def test_get_policy_not_found(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.get_policy("bad")

    def test_escalation_chain(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        now = time.time()
        self.mgr.add_slot(RotationSlot(
            person_id=alice.id, start_epoch=now - 100, end_epoch=now + 100,
            level=EscalationLevel.PRIMARY,
        ))
        self.mgr.add_slot(RotationSlot(
            person_id=bob.id, start_epoch=now - 100, end_epoch=now + 100,
            level=EscalationLevel.SECONDARY,
        ))
        pol = self.mgr.add_policy(EscalationPolicy(name="esc"))
        chain = self.mgr.escalation_chain(pol.id)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0].name, "Alice")
        self.assertEqual(chain[1].name, "Bob")

    def test_record_fatigue(self) -> None:
        p = self._add_person()
        rec = self.mgr.record_fatigue(p.id, hours=8, incidents=2, pages=5)
        self.assertEqual(rec.hours_on_call, 8)
        self.assertEqual(rec.incidents_handled, 2)
        self.assertEqual(rec.pages_received, 5)
        self.assertIsNotNone(rec.last_paged_at)

    def test_record_fatigue_accumulates(self) -> None:
        p = self._add_person()
        self.mgr.record_fatigue(p.id, hours=4)
        rec = self.mgr.record_fatigue(p.id, hours=4)
        self.assertEqual(rec.hours_on_call, 8)

    def test_record_fatigue_bad_person(self) -> None:
        with self.assertRaises(OnCallError):
            self.mgr.record_fatigue("nope")

    def test_get_fatigue_default(self) -> None:
        p = self._add_person()
        rec = self.mgr.get_fatigue(p.id)
        self.assertEqual(rec.hours_on_call, 0)

    def test_create_handoff(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        note = self.mgr.create_handoff(alice.id, bob.id, "All clear", ["TICKET-1"])
        self.assertEqual(note.content, "All clear")
        self.assertEqual(len(note.open_issues), 1)

    def test_create_handoff_bad_person(self) -> None:
        alice = self._add_person("Alice")
        with self.assertRaises(OnCallError):
            self.mgr.create_handoff(alice.id, "bad", "notes")

    def test_create_handoff_bad_from(self) -> None:
        bob = self._add_person("Bob")
        with self.assertRaises(OnCallError):
            self.mgr.create_handoff("bad", bob.id, "notes")

    def test_list_handoffs(self) -> None:
        alice = self._add_person("Alice")
        bob = self._add_person("Bob")
        self.mgr.create_handoff(alice.id, bob.id, "note")
        self.assertEqual(len(self.mgr.list_handoffs()), 1)
        self.assertEqual(len(self.mgr.list_handoffs(alice.id)), 1)
        self.assertEqual(len(self.mgr.list_handoffs(bob.id)), 1)


if __name__ == "__main__":
    unittest.main()
