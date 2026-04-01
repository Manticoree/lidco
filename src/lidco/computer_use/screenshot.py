"""Screenshot capture and analysis (simulated)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScreenRegion:
    """A rectangular region on screen."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a simulated screenshot capture."""

    width: int
    height: int
    format: str = "png"
    regions: tuple[ScreenRegion, ...] = ()
    text_content: str = ""
    timestamp: float = 0.0


class ScreenshotAnalyzer:
    """Simulated screenshot capture and analysis."""

    def __init__(self) -> None:
        self._history: list[ScreenshotResult] = []

    def capture(self, region: ScreenRegion | None = None) -> ScreenshotResult:
        """Simulate a screenshot capture."""
        if region is not None:
            result = ScreenshotResult(
                width=region.width,
                height=region.height,
                format="png",
                regions=(region,),
                text_content="",
                timestamp=time.time(),
            )
        else:
            result = ScreenshotResult(
                width=1920,
                height=1080,
                format="png",
                regions=(),
                text_content="",
                timestamp=time.time(),
            )
        self._history.append(result)
        return result

    def extract_text(self, result: ScreenshotResult) -> str:
        """Extract text content from a screenshot result."""
        return result.text_content

    def find_element(self, result: ScreenshotResult, label: str) -> ScreenRegion | None:
        """Find a named element within screenshot regions.

        Matches if *label* appears in the region's string representation.
        For simulated purposes, checks region metadata via a simple heuristic:
        returns the first region whose coordinates encode the label hash, or *None*.
        """
        # In simulation, we look for a region tagged via text_content
        if label.lower() in result.text_content.lower():
            if result.regions:
                return result.regions[0]
            return ScreenRegion(x=0, y=0, width=100, height=30)
        return None

    def compare(self, result1: ScreenshotResult, result2: ScreenshotResult) -> float:
        """Return similarity score (0-1) between two screenshots."""
        if result1.width != result2.width or result1.height != result2.height:
            return 0.0
        if result1.text_content == result2.text_content and result1.regions == result2.regions:
            return 1.0
        # partial similarity based on matching text
        if result1.text_content and result2.text_content:
            common = set(result1.text_content.split()) & set(result2.text_content.split())
            total = set(result1.text_content.split()) | set(result2.text_content.split())
            if total:
                return len(common) / len(total)
        return 0.5

    def history(self) -> list[ScreenshotResult]:
        """Return all captured screenshots."""
        return list(self._history)
