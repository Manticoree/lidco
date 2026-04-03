"""Tests for lidco.notify.sound."""
from __future__ import annotations

import unittest

from lidco.notify.sound import SoundEngine, SoundEvent


class TestSoundEvent(unittest.TestCase):
    def test_frozen_dataclass(self):
        e = SoundEvent(name="beep")
        self.assertIsNone(e.sound_file)
        with self.assertRaises(AttributeError):
            e.name = "x"  # type: ignore[misc]


class TestSoundEngine(unittest.TestCase):
    def test_play_records_event(self):
        engine = SoundEngine()
        ev = engine.play("completion")
        self.assertEqual(ev.name, "completion")
        self.assertIsNone(ev.sound_file)
        self.assertGreater(ev.timestamp, 0)

    def test_play_with_registered_sound(self):
        engine = SoundEngine()
        engine.register_sound("ding", "/sounds/ding.wav")
        ev = engine.play("ding")
        self.assertEqual(ev.sound_file, "/sounds/ding.wav")

    def test_mute_unmute(self):
        engine = SoundEngine()
        self.assertFalse(engine.is_muted())
        engine.mute()
        self.assertTrue(engine.is_muted())
        engine.unmute()
        self.assertFalse(engine.is_muted())

    def test_init_muted(self):
        engine = SoundEngine(muted=True)
        self.assertTrue(engine.is_muted())

    def test_available_events_default(self):
        engine = SoundEngine()
        events = engine.available_events()
        self.assertIn("completion", events)
        self.assertIn("error", events)
        self.assertIn("warning", events)
        self.assertIn("notification", events)

    def test_available_events_with_registered(self):
        engine = SoundEngine()
        engine.register_sound("custom_beep", "/beep.wav")
        events = engine.available_events()
        self.assertIn("custom_beep", events)

    def test_register_overwrites(self):
        engine = SoundEngine()
        engine.register_sound("completion", "/v1.wav")
        engine.register_sound("completion", "/v2.wav")
        ev = engine.play("completion")
        self.assertEqual(ev.sound_file, "/v2.wav")

    def test_history(self):
        engine = SoundEngine()
        engine.play("a")
        engine.play("b")
        self.assertEqual(len(engine.history()), 2)

    def test_history_is_copy(self):
        engine = SoundEngine()
        engine.play("a")
        h = engine.history()
        h.clear()
        self.assertEqual(len(engine.history()), 1)

    def test_summary(self):
        engine = SoundEngine()
        engine.register_sound("x", "/x.wav")
        engine.play("x")
        s = engine.summary()
        self.assertEqual(s["registered"], 1)
        self.assertEqual(s["played"], 1)
        self.assertFalse(s["muted"])


if __name__ == "__main__":
    unittest.main()
