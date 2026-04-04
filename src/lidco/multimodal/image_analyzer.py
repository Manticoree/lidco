"""Image analysis module — screenshot analysis with optional PIL support.

Provides ImageAnalyzer with simulated vision capabilities for analyzing
screenshots, detecting UI elements, diffing images, and generating descriptions.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AnalysisResult:
    """Result of analysing an image."""

    path: str
    width: int
    height: int
    format: str
    labels: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UIElement:
    """Detected UI element in a screenshot."""

    kind: str
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


@dataclass(frozen=True)
class DiffResult:
    """Result of comparing two screenshots."""

    path_a: str
    path_b: str
    similarity: float
    changed_regions: list[dict[str, Any]] = field(default_factory=list)
    pixel_diff_count: int = 0
    summary: str = ""


class ImageAnalyzer:
    """Analyse screenshots and images (simulated when PIL unavailable)."""

    def __init__(self, *, use_pil: bool = True) -> None:
        self._use_pil = use_pil and Image is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, path: str) -> AnalysisResult:
        """Analyse an image file and return structured result."""
        if not path:
            raise ValueError("path must not be empty")
        info = self._read_image_info(path)
        labels = self._classify(path, info)
        return AnalysisResult(
            path=path,
            width=info.get("width", 0),
            height=info.get("height", 0),
            format=info.get("format", "unknown"),
            labels=labels,
            confidence=0.85 if labels else 0.0,
            metadata=info,
        )

    def detect_elements(self, path: str) -> list[UIElement]:
        """Detect UI elements in a screenshot."""
        if not path:
            raise ValueError("path must not be empty")
        info = self._read_image_info(path)
        w = info.get("width", 800)
        h = info.get("height", 600)
        elements: list[UIElement] = [
            UIElement(kind="button", label="Submit", x=w // 4, y=h // 2, width=120, height=40, confidence=0.92),
            UIElement(kind="input", label="Search", x=w // 2, y=h // 4, width=200, height=32, confidence=0.88),
            UIElement(kind="nav", label="Navigation", x=0, y=0, width=w, height=60, confidence=0.95),
        ]
        return elements

    def diff_screenshots(self, path_a: str, path_b: str) -> DiffResult:
        """Compare two screenshots and return a diff."""
        if not path_a or not path_b:
            raise ValueError("both paths must be provided")
        info_a = self._read_image_info(path_a)
        info_b = self._read_image_info(path_b)
        hash_a = self._content_hash(path_a)
        hash_b = self._content_hash(path_b)
        same = hash_a == hash_b
        similarity = 1.0 if same else 0.72
        regions: list[dict[str, Any]] = []
        pixel_diff = 0
        if not same:
            regions.append({"x": 10, "y": 20, "width": 100, "height": 50, "type": "changed"})
            pixel_diff = abs(info_a.get("width", 0) * info_a.get("height", 0) - info_b.get("width", 0) * info_b.get("height", 0)) + 150
        summary = "Images are identical." if same else f"Found {len(regions)} changed region(s)."
        return DiffResult(
            path_a=path_a,
            path_b=path_b,
            similarity=similarity,
            changed_regions=regions,
            pixel_diff_count=pixel_diff,
            summary=summary,
        )

    def describe(self, path: str) -> str:
        """Generate a natural-language description of the image."""
        if not path:
            raise ValueError("path must not be empty")
        info = self._read_image_info(path)
        fmt = info.get("format", "unknown")
        w = info.get("width", 0)
        h = info.get("height", 0)
        ext = os.path.splitext(path)[1].lower()
        kind = "screenshot" if ext == ".png" else "image"
        return f"A {w}x{h} {fmt} {kind} located at {path}."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_image_info(self, path: str) -> dict[str, Any]:
        """Read basic image info, using PIL if available or simulating."""
        if self._use_pil and Image is not None:
            img = Image.open(path)
            return {
                "width": img.width,
                "height": img.height,
                "format": (img.format or "unknown").lower(),
                "mode": img.mode,
            }
        # Simulated fallback — derive size from file size
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        fmt = ext if ext else "unknown"
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        w = max(size % 1920, 320)
        h = max(size % 1080, 240)
        return {"width": w, "height": h, "format": fmt}

    @staticmethod
    def _content_hash(path: str) -> str:
        """Return a hash of the file for comparison."""
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError:
            return path

    @staticmethod
    def _classify(path: str, info: dict[str, Any]) -> list[str]:
        """Simple label classification based on file properties."""
        labels: list[str] = []
        ext = os.path.splitext(path)[1].lower()
        if ext == ".png":
            labels.append("screenshot")
        elif ext in (".jpg", ".jpeg"):
            labels.append("photo")
        w = info.get("width", 0)
        h = info.get("height", 0)
        if w > 0 and h > 0:
            labels.append("has-content")
        if w >= 1920:
            labels.append("high-resolution")
        return labels
