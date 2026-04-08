"""Visual Diff Engine — pixel-by-pixel comparison, perceptual hash,
tolerance thresholds, highlight changes, and masking."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any

try:
    from PIL import Image  # type: ignore[import-untyped]
except ImportError:
    Image = None  # type: ignore[assignment]


# ---- Data classes --------------------------------------------------------


@dataclass(frozen=True)
class MaskRegion:
    """Rectangle to exclude from comparison (x, y, width, height)."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


@dataclass(frozen=True)
class DiffOptions:
    """Options for visual comparison."""

    tolerance: float = 0.0  # 0.0–1.0 per-channel tolerance (fraction of 255)
    threshold: float = 0.01  # max fraction of diff pixels to still pass
    anti_aliasing: bool = False
    masks: list[MaskRegion] = field(default_factory=list)
    highlight_color: tuple[int, int, int, int] = (255, 0, 0, 255)


@dataclass(frozen=True)
class DiffResult:
    """Result of a visual diff."""

    match: bool
    total_pixels: int
    diff_pixels: int
    diff_percentage: float
    dimensions_match: bool
    baseline_size: tuple[int, int]
    current_size: tuple[int, int]
    diff_image_bytes: bytes = b""
    perceptual_hash_baseline: str = ""
    perceptual_hash_current: str = ""
    error: str = ""


# ---- Helpers -------------------------------------------------------------


def _parse_raw_pixels(data: bytes, width: int, height: int) -> list[tuple[int, ...]]:
    """Parse raw RGBA pixel data (4 bytes per pixel) into a list of tuples."""
    expected = width * height * 4
    if len(data) < expected:
        padded = data + b"\x00" * (expected - len(data))
    else:
        padded = data[:expected]
    pixels: list[tuple[int, ...]] = []
    for i in range(0, expected, 4):
        pixels.append(struct.unpack("BBBB", padded[i : i + 4]))
    return pixels


def _pixels_differ(
    a: tuple[int, ...], b: tuple[int, ...], tolerance: float,
) -> bool:
    """Return True if any channel differs by more than tolerance * 255."""
    tol = int(tolerance * 255)
    for ca, cb in zip(a[:3], b[:3]):
        if abs(ca - cb) > tol:
            return True
    return False


def _is_masked(px: int, py: int, masks: list[MaskRegion]) -> bool:
    for m in masks:
        if m.contains(px, py):
            return True
    return False


def perceptual_hash(data: bytes, width: int, height: int, hash_size: int = 8) -> str:
    """Compute a simple average-hash (aHash) from raw RGBA pixel data.

    Resizes to *hash_size x hash_size* by nearest-neighbour sampling,
    then computes a binary hash based on average luminance.
    """
    pixels = _parse_raw_pixels(data, width, height)
    if not pixels:
        return ""

    # Nearest-neighbour downsample to hash_size x hash_size grayscale
    grey: list[int] = []
    for row in range(hash_size):
        src_y = int(row * height / hash_size)
        for col in range(hash_size):
            src_x = int(col * width / hash_size)
            idx = src_y * width + src_x
            if idx < len(pixels):
                r, g, b = pixels[idx][0], pixels[idx][1], pixels[idx][2]
                grey.append((r + g + b) // 3)
            else:
                grey.append(0)

    avg = sum(grey) // len(grey) if grey else 0
    bits = "".join("1" if v >= avg else "0" for v in grey)
    # Convert bit-string to hex
    hex_str = ""
    for i in range(0, len(bits), 4):
        nibble = bits[i : i + 4].ljust(4, "0")
        hex_str += format(int(nibble, 2), "x")
    return hex_str


# ---- VisualDiffEngine ----------------------------------------------------


class VisualDiffEngine:
    """Compare two images pixel-by-pixel with tolerance, masking, and perceptual hashing."""

    def __init__(self, default_options: DiffOptions | None = None) -> None:
        self._default = default_options or DiffOptions()

    @property
    def default_options(self) -> DiffOptions:
        return self._default

    def compare_raw(
        self,
        baseline: bytes,
        current: bytes,
        width: int,
        height: int,
        options: DiffOptions | None = None,
    ) -> DiffResult:
        """Compare two raw RGBA buffers of identical dimensions."""
        opts = options or self._default
        total = width * height
        if total == 0:
            return DiffResult(
                match=True, total_pixels=0, diff_pixels=0, diff_percentage=0.0,
                dimensions_match=True, baseline_size=(width, height),
                current_size=(width, height),
            )

        base_px = _parse_raw_pixels(baseline, width, height)
        curr_px = _parse_raw_pixels(current, width, height)

        diff_count = 0
        highlight = bytearray()
        hc = opts.highlight_color

        for idx in range(total):
            py, px_coord = divmod(idx, width)
            if _is_masked(px_coord, py, opts.masks):
                highlight.extend(bytes([0, 0, 0, 0]))
                continue
            if _pixels_differ(base_px[idx], curr_px[idx], opts.tolerance):
                diff_count += 1
                highlight.extend(bytes(hc))
            else:
                highlight.extend(bytes([0, 0, 0, 0]))

        pct = diff_count / total if total > 0 else 0.0
        passed = pct <= opts.threshold

        return DiffResult(
            match=passed,
            total_pixels=total,
            diff_pixels=diff_count,
            diff_percentage=round(pct * 100, 4),
            dimensions_match=True,
            baseline_size=(width, height),
            current_size=(width, height),
            diff_image_bytes=bytes(highlight),
            perceptual_hash_baseline=perceptual_hash(baseline, width, height),
            perceptual_hash_current=perceptual_hash(current, width, height),
        )

    def compare_dimensions(
        self,
        baseline_size: tuple[int, int],
        current_size: tuple[int, int],
    ) -> DiffResult | None:
        """Quick check: return a failure DiffResult if dimensions differ, else None."""
        if baseline_size != current_size:
            return DiffResult(
                match=False,
                total_pixels=0,
                diff_pixels=0,
                diff_percentage=100.0,
                dimensions_match=False,
                baseline_size=baseline_size,
                current_size=current_size,
                error=f"Dimension mismatch: {baseline_size} vs {current_size}",
            )
        return None

    def hamming_distance(self, hash_a: str, hash_b: str) -> int:
        """Compute hamming distance between two hex-encoded perceptual hashes."""
        if len(hash_a) != len(hash_b):
            return max(len(hash_a), len(hash_b)) * 4
        dist = 0
        for ca, cb in zip(hash_a, hash_b):
            diff = int(ca, 16) ^ int(cb, 16)
            dist += bin(diff).count("1")
        return dist
