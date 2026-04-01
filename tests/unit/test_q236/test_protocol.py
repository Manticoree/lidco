"""Tests for teleport.protocol."""
from __future__ import annotations

import unittest

from lidco.teleport.protocol import Chunk, TransferProtocol, TransferSession


class TestChunk(unittest.TestCase):
    def test_frozen(self) -> None:
        c = Chunk(index=0, data="hello")
        with self.assertRaises(AttributeError):
            c.index = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        c = Chunk(index=0, data="x")
        self.assertEqual(c.checksum, "")
        self.assertEqual(c.total_chunks, 0)


class TestTransferSession(unittest.TestCase):
    def test_frozen(self) -> None:
        s = TransferSession(id="t1")
        with self.assertRaises(AttributeError):
            s.id = "t2"  # type: ignore[misc]


class TestTransferProtocol(unittest.TestCase):
    def setUp(self) -> None:
        self.proto = TransferProtocol(chunk_size=10)

    def test_split_small_data(self) -> None:
        chunks = self.proto.split("hello")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].data, "hello")
        self.assertEqual(chunks[0].index, 0)
        self.assertEqual(chunks[0].total_chunks, 1)
        self.assertNotEqual(chunks[0].checksum, "")

    def test_split_multi_chunks(self) -> None:
        data = "a" * 25
        chunks = self.proto.split(data)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].total_chunks, 3)

    def test_split_empty(self) -> None:
        self.assertEqual(self.proto.split(""), [])

    def test_reassemble_roundtrip(self) -> None:
        data = "Hello, this is a test of the chunked protocol!"
        chunks = self.proto.split(data)
        result = self.proto.reassemble(chunks)
        self.assertEqual(result, data)

    def test_reassemble_incomplete_returns_none(self) -> None:
        data = "abcdefghij" * 3
        chunks = self.proto.split(data)
        result = self.proto.reassemble(chunks[:1])
        self.assertIsNone(result)

    def test_reassemble_bad_checksum_returns_none(self) -> None:
        chunks = self.proto.split("hello world!")
        bad = Chunk(index=0, data=chunks[0].data, checksum="bad", total_chunks=chunks[0].total_chunks)
        result = self.proto.reassemble([bad] + chunks[1:])
        self.assertIsNone(result)

    def test_verify_chunk_valid(self) -> None:
        chunks = self.proto.split("test")
        self.assertTrue(self.proto.verify_chunk(chunks[0]))

    def test_verify_chunk_empty_checksum(self) -> None:
        c = Chunk(index=0, data="hello")
        self.assertTrue(self.proto.verify_chunk(c))

    def test_create_session(self) -> None:
        session = self.proto.create_session(5)
        self.assertEqual(session.total_chunks, 5)
        self.assertEqual(session.received, 0)
        self.assertFalse(session.complete)

    def test_progress(self) -> None:
        session = TransferSession(id="t1", total_chunks=4, received=2)
        self.assertAlmostEqual(self.proto.progress(session), 0.5)

    def test_progress_zero_total(self) -> None:
        session = TransferSession(id="t1", total_chunks=0)
        self.assertAlmostEqual(self.proto.progress(session), 1.0)

    def test_summary(self) -> None:
        s = self.proto.summary()
        self.assertIn("10", s)
