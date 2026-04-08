"""Tests for visual_test/diff.py — VisualDiffEngine."""

import unittest

from lidco.visual_test.diff import (
    DiffOptions,
    DiffResult,
    MaskRegion,
    VisualDiffEngine,
    _is_masked,
    _parse_raw_pixels,
    _pixels_differ,
    perceptual_hash,
)


class TestMaskRegion(unittest.TestCase):
    def test_contains_inside(self):
        m = MaskRegion(x=10, y=10, width=20, height=20)
        self.assertTrue(m.contains(15, 15))

    def test_contains_edge(self):
        m = MaskRegion(x=10, y=10, width=20, height=20)
        self.assertTrue(m.contains(10, 10))

    def test_not_contains_outside(self):
        m = MaskRegion(x=10, y=10, width=20, height=20)
        self.assertFalse(m.contains(5, 5))

    def test_not_contains_right_edge(self):
        m = MaskRegion(x=10, y=10, width=20, height=20)
        self.assertFalse(m.contains(30, 15))


class TestDiffOptions(unittest.TestCase):
    def test_defaults(self):
        opts = DiffOptions()
        self.assertEqual(opts.tolerance, 0.0)
        self.assertEqual(opts.threshold, 0.01)
        self.assertFalse(opts.anti_aliasing)
        self.assertEqual(opts.masks, [])
        self.assertEqual(opts.highlight_color, (255, 0, 0, 255))

    def test_custom(self):
        opts = DiffOptions(tolerance=0.1, threshold=0.05)
        self.assertEqual(opts.tolerance, 0.1)
        self.assertEqual(opts.threshold, 0.05)


class TestParseRawPixels(unittest.TestCase):
    def test_single_pixel(self):
        data = bytes([255, 0, 0, 255])  # red
        pixels = _parse_raw_pixels(data, 1, 1)
        self.assertEqual(len(pixels), 1)
        self.assertEqual(pixels[0], (255, 0, 0, 255))

    def test_two_pixels(self):
        data = bytes([255, 0, 0, 255, 0, 255, 0, 255])
        pixels = _parse_raw_pixels(data, 2, 1)
        self.assertEqual(len(pixels), 2)

    def test_short_data_padded(self):
        data = bytes([255, 0])
        pixels = _parse_raw_pixels(data, 1, 1)
        self.assertEqual(len(pixels), 1)

    def test_empty(self):
        pixels = _parse_raw_pixels(b"", 0, 0)
        self.assertEqual(pixels, [])


class TestPixelsDiffer(unittest.TestCase):
    def test_identical(self):
        a = (100, 100, 100, 255)
        self.assertFalse(_pixels_differ(a, a, 0.0))

    def test_different(self):
        a = (100, 100, 100, 255)
        b = (200, 100, 100, 255)
        self.assertTrue(_pixels_differ(a, b, 0.0))

    def test_within_tolerance(self):
        a = (100, 100, 100, 255)
        b = (105, 100, 100, 255)
        self.assertFalse(_pixels_differ(a, b, 0.05))  # tol = 12.75

    def test_outside_tolerance(self):
        a = (100, 100, 100, 255)
        b = (120, 100, 100, 255)
        self.assertTrue(_pixels_differ(a, b, 0.05))


class TestIsMasked(unittest.TestCase):
    def test_no_masks(self):
        self.assertFalse(_is_masked(5, 5, []))

    def test_inside_mask(self):
        masks = [MaskRegion(0, 0, 10, 10)]
        self.assertTrue(_is_masked(5, 5, masks))

    def test_outside_mask(self):
        masks = [MaskRegion(0, 0, 10, 10)]
        self.assertFalse(_is_masked(15, 15, masks))

    def test_multiple_masks(self):
        masks = [MaskRegion(0, 0, 5, 5), MaskRegion(10, 10, 5, 5)]
        self.assertTrue(_is_masked(12, 12, masks))
        self.assertFalse(_is_masked(7, 7, masks))


class TestPerceptualHash(unittest.TestCase):
    def test_deterministic(self):
        data = bytes([128] * 16)  # 2x2 RGBA
        h1 = perceptual_hash(data, 2, 2)
        h2 = perceptual_hash(data, 2, 2)
        self.assertEqual(h1, h2)

    def test_different_images(self):
        white = bytes([255, 255, 255, 255] * 4)
        black = bytes([0, 0, 0, 255] * 4)
        h1 = perceptual_hash(white, 2, 2)
        h2 = perceptual_hash(black, 2, 2)
        # Hashes may or may not differ for uniform images,
        # but the function should not crash
        self.assertIsInstance(h1, str)
        self.assertIsInstance(h2, str)

    def test_empty(self):
        h = perceptual_hash(b"", 0, 0)
        self.assertEqual(h, "")

    def test_returns_hex_string(self):
        data = bytes(range(256)) * 4  # 16x16 RGBA (requires 16*16*4=1024 bytes)
        h = perceptual_hash(data, 16, 16)
        self.assertGreater(len(h), 0)
        # Should be valid hex
        int(h, 16)


class TestVisualDiffEngine(unittest.TestCase):
    def test_init_default(self):
        engine = VisualDiffEngine()
        self.assertEqual(engine.default_options.tolerance, 0.0)

    def test_identical_images(self):
        engine = VisualDiffEngine()
        data = bytes([100, 100, 100, 255] * 4)  # 2x2
        result = engine.compare_raw(data, data, 2, 2)
        self.assertTrue(result.match)
        self.assertEqual(result.diff_pixels, 0)
        self.assertEqual(result.diff_percentage, 0.0)
        self.assertTrue(result.dimensions_match)

    def test_completely_different(self):
        engine = VisualDiffEngine()
        base = bytes([0, 0, 0, 255] * 4)
        curr = bytes([255, 255, 255, 255] * 4)
        result = engine.compare_raw(base, curr, 2, 2)
        self.assertFalse(result.match)
        self.assertEqual(result.diff_pixels, 4)
        self.assertEqual(result.diff_percentage, 100.0)

    def test_one_pixel_diff(self):
        engine = VisualDiffEngine()
        base = bytes([100, 100, 100, 255] * 4)
        curr = bytearray(base)
        curr[0] = 200  # change first pixel R channel
        result = engine.compare_raw(base, bytes(curr), 2, 2)
        self.assertEqual(result.diff_pixels, 1)
        self.assertAlmostEqual(result.diff_percentage, 25.0, places=1)

    def test_with_tolerance(self):
        engine = VisualDiffEngine()
        base = bytes([100, 100, 100, 255] * 4)
        curr = bytes([105, 100, 100, 255] * 4)
        opts = DiffOptions(tolerance=0.05, threshold=1.0)
        result = engine.compare_raw(base, curr, 2, 2, opts)
        self.assertTrue(result.match)
        self.assertEqual(result.diff_pixels, 0)

    def test_with_mask(self):
        engine = VisualDiffEngine()
        base = bytes([0, 0, 0, 255] * 4)
        curr = bytes([255, 255, 255, 255] * 4)
        # Mask the entire 2x2 image
        opts = DiffOptions(masks=[MaskRegion(0, 0, 2, 2)], threshold=0.01)
        result = engine.compare_raw(base, curr, 2, 2, opts)
        self.assertTrue(result.match)
        self.assertEqual(result.diff_pixels, 0)

    def test_zero_size(self):
        engine = VisualDiffEngine()
        result = engine.compare_raw(b"", b"", 0, 0)
        self.assertTrue(result.match)
        self.assertEqual(result.total_pixels, 0)

    def test_diff_image_bytes_produced(self):
        engine = VisualDiffEngine()
        base = bytes([0, 0, 0, 255] * 4)
        curr = bytes([255, 0, 0, 255] * 4)
        result = engine.compare_raw(base, curr, 2, 2)
        # diff_image_bytes = 4 pixels * 4 bytes each
        self.assertEqual(len(result.diff_image_bytes), 16)

    def test_perceptual_hashes_populated(self):
        engine = VisualDiffEngine()
        data = bytes([100, 100, 100, 255] * 4)
        result = engine.compare_raw(data, data, 2, 2)
        self.assertGreater(len(result.perceptual_hash_baseline), 0)
        self.assertEqual(result.perceptual_hash_baseline, result.perceptual_hash_current)

    def test_compare_dimensions_match(self):
        engine = VisualDiffEngine()
        result = engine.compare_dimensions((100, 100), (100, 100))
        self.assertIsNone(result)

    def test_compare_dimensions_mismatch(self):
        engine = VisualDiffEngine()
        result = engine.compare_dimensions((100, 100), (200, 200))
        self.assertIsNotNone(result)
        self.assertFalse(result.match)
        self.assertFalse(result.dimensions_match)
        self.assertIn("mismatch", result.error.lower())

    def test_hamming_distance_identical(self):
        engine = VisualDiffEngine()
        self.assertEqual(engine.hamming_distance("abcd", "abcd"), 0)

    def test_hamming_distance_different(self):
        engine = VisualDiffEngine()
        d = engine.hamming_distance("0000", "ffff")
        self.assertGreater(d, 0)

    def test_hamming_distance_length_mismatch(self):
        engine = VisualDiffEngine()
        d = engine.hamming_distance("00", "0000")
        self.assertGreater(d, 0)

    def test_custom_highlight_color(self):
        engine = VisualDiffEngine()
        opts = DiffOptions(highlight_color=(0, 255, 0, 128))
        base = bytes([0, 0, 0, 255])
        curr = bytes([255, 255, 255, 255])
        result = engine.compare_raw(base, curr, 1, 1, opts)
        # The diff image should contain the green highlight
        self.assertEqual(result.diff_image_bytes, bytes([0, 255, 0, 128]))


if __name__ == "__main__":
    unittest.main()
