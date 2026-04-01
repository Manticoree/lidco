"""Tests for teleport.serializer."""
from __future__ import annotations

import json
import unittest

from lidco.teleport.serializer import SessionSerializer, SessionSnapshot


class TestSessionSnapshot(unittest.TestCase):
    def test_frozen(self) -> None:
        snap = SessionSnapshot(session_id="s1")
        with self.assertRaises(AttributeError):
            snap.session_id = "s2"  # type: ignore[misc]

    def test_defaults(self) -> None:
        snap = SessionSnapshot(session_id="s1")
        self.assertEqual(snap.version, "1.0")
        self.assertEqual(snap.messages, ())
        self.assertEqual(snap.files, ())
        self.assertEqual(snap.config, ())
        self.assertEqual(snap.checksum, "")
        self.assertIsInstance(snap.timestamp, float)


class TestSessionSerializer(unittest.TestCase):
    def setUp(self) -> None:
        self.ser = SessionSerializer()

    def test_serialize_basic(self) -> None:
        snap = self.ser.serialize("s1", [{"role": "user", "content": "hi"}])
        self.assertEqual(snap.session_id, "s1")
        self.assertEqual(len(snap.messages), 1)
        self.assertNotEqual(snap.checksum, "")

    def test_serialize_with_files_and_config(self) -> None:
        snap = self.ser.serialize(
            "s2", [], files=["a.py", "b.py"], config={"model": "gpt-4"},
        )
        self.assertEqual(snap.files, ("a.py", "b.py"))
        self.assertEqual(snap.config, (("model", "gpt-4"),))

    def test_to_json_roundtrip(self) -> None:
        snap = self.ser.serialize("s3", [{"role": "user", "content": "hello"}])
        js = self.ser.to_json(snap)
        restored = self.ser.from_json(js)
        self.assertEqual(restored.session_id, snap.session_id)
        self.assertEqual(restored.messages, snap.messages)
        self.assertEqual(restored.checksum, snap.checksum)

    def test_from_json_bad_checksum_raises(self) -> None:
        snap = self.ser.serialize("s4", [{"role": "user", "content": "x"}])
        js = self.ser.to_json(snap)
        obj = json.loads(js)
        obj["checksum"] = "bad"
        with self.assertRaises(ValueError):
            self.ser.from_json(json.dumps(obj))

    def test_compress_decompress(self) -> None:
        original = "Hello world! " * 100
        compressed = self.ser.compress(original)
        self.assertIsInstance(compressed, bytes)
        self.assertLess(len(compressed), len(original.encode()))
        restored = self.ser.decompress(compressed)
        self.assertEqual(restored, original)

    def test_verify_checksum_valid(self) -> None:
        snap = self.ser.serialize("s5", [{"role": "assistant", "content": "ok"}])
        self.assertTrue(self.ser.verify_checksum(snap))

    def test_verify_checksum_invalid(self) -> None:
        snap = SessionSnapshot(session_id="s6", checksum="wrong")
        self.assertFalse(self.ser.verify_checksum(snap))

    def test_summary(self) -> None:
        snap = self.ser.serialize("s7", [{"role": "user", "content": "a"}])
        s = self.ser.summary(snap)
        self.assertIn("s7", s)
        self.assertIn("1 messages", s)

    def test_schema_version(self) -> None:
        ser2 = SessionSerializer(schema_version="2.0")
        snap = ser2.serialize("s8", [])
        self.assertEqual(snap.version, "2.0")

    def test_empty_messages(self) -> None:
        snap = self.ser.serialize("s9", [])
        self.assertEqual(snap.messages, ())
        js = self.ser.to_json(snap)
        restored = self.ser.from_json(js)
        self.assertEqual(restored.messages, ())

    def test_config_sorted(self) -> None:
        snap = self.ser.serialize("s10", [], config={"z": "1", "a": "2"})
        self.assertEqual(snap.config, (("a", "2"), ("z", "1")))
