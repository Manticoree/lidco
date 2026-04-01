"""Tests for cache.token_compressor — CompressionResult, TokenCompressor."""
from __future__ import annotations

import unittest

from lidco.cache.token_compressor import CompressionResult, TokenCompressor


class TestCompressionResult(unittest.TestCase):
    def test_frozen(self):
        r = CompressionResult(original_tokens=100, compressed_tokens=80, ratio=0.8, text="t")
        with self.assertRaises(AttributeError):
            r.text = "x"  # type: ignore[misc]

    def test_fields(self):
        r = CompressionResult(50, 30, 0.6, "compressed")
        self.assertEqual(r.original_tokens, 50)
        self.assertEqual(r.compressed_tokens, 30)
        self.assertAlmostEqual(r.ratio, 0.6)
        self.assertEqual(r.text, "compressed")

    def test_equality(self):
        a = CompressionResult(10, 5, 0.5, "t")
        b = CompressionResult(10, 5, 0.5, "t")
        self.assertEqual(a, b)


class TestTokenCompressor(unittest.TestCase):
    def test_compress_basic(self):
        tc = TokenCompressor()
        result = tc.compress("hello   world")
        self.assertIn("hello world", result.text)
        self.assertLessEqual(result.compressed_tokens, result.original_tokens)

    def test_compress_blank_lines(self):
        tc = TokenCompressor()
        text = "line1\n\n\n\n\nline2"
        result = tc.compress(text)
        self.assertNotIn("\n\n\n", result.text)
        self.assertIn("line1", result.text)
        self.assertIn("line2", result.text)

    def test_compress_returns_compression_result(self):
        tc = TokenCompressor()
        result = tc.compress("some text")
        self.assertIsInstance(result, CompressionResult)

    def test_compress_ratio_range(self):
        tc = TokenCompressor()
        result = tc.compress("a   b   c   d")
        self.assertGreater(result.ratio, 0.0)
        self.assertLessEqual(result.ratio, 1.0)

    def test_compress_already_compact(self):
        tc = TokenCompressor()
        result = tc.compress("compact text")
        self.assertAlmostEqual(result.ratio, 1.0, places=1)

    def test_dedup_reads_empty(self):
        tc = TokenCompressor()
        self.assertEqual(tc.dedup_reads(()), ())

    def test_dedup_reads_no_duplicates(self):
        tc = TokenCompressor()
        entries = ("a", "b", "c")
        self.assertEqual(tc.dedup_reads(entries), entries)

    def test_dedup_reads_with_duplicates(self):
        tc = TokenCompressor()
        entries = ("a", "b", "a", "c", "b")
        result = tc.dedup_reads(entries)
        self.assertEqual(result, ("a", "b", "c"))

    def test_dedup_reads_preserves_order(self):
        tc = TokenCompressor()
        entries = ("b", "a", "b", "a")
        self.assertEqual(tc.dedup_reads(entries), ("b", "a"))

    def test_dedup_reads_returns_tuple(self):
        tc = TokenCompressor()
        result = tc.dedup_reads(("a", "a"))
        self.assertIsInstance(result, tuple)

    def test_summarize_pattern_empty(self):
        tc = TokenCompressor()
        self.assertEqual(tc.summarize_pattern(()), "")

    def test_summarize_pattern_single(self):
        tc = TokenCompressor()
        result = tc.summarize_pattern(("hello",))
        self.assertEqual(result, "hello")

    def test_summarize_pattern_common_prefix(self):
        tc = TokenCompressor()
        texts = ("prefix_a", "prefix_b", "prefix_c")
        result = tc.summarize_pattern(texts)
        self.assertIn("prefix", result.lower())
        self.assertIn("3 variants", result)

    def test_summarize_pattern_no_common(self):
        tc = TokenCompressor()
        texts = ("abc", "xyz")
        result = tc.summarize_pattern(texts)
        self.assertIn("2 variants", result)

    def test_compress_strips_whitespace(self):
        tc = TokenCompressor()
        result = tc.compress("  hello  ")
        self.assertEqual(result.text, "hello")

    def test_compress_empty_string(self):
        tc = TokenCompressor()
        result = tc.compress("")
        self.assertEqual(result.text, "")

    def test_dedup_reads_all_same(self):
        tc = TokenCompressor()
        entries = ("a", "a", "a")
        self.assertEqual(tc.dedup_reads(entries), ("a",))

    def test_compression_result_different_not_equal(self):
        a = CompressionResult(10, 5, 0.5, "a")
        b = CompressionResult(10, 5, 0.5, "b")
        self.assertNotEqual(a, b)


class TestTokenCompressorAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.cache import token_compressor

        self.assertIn("CompressionResult", token_compressor.__all__)
        self.assertIn("TokenCompressor", token_compressor.__all__)


if __name__ == "__main__":
    unittest.main()
