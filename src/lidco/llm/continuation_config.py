"""Configuration helpers for the prefill continuation engine."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContinuationConfig:
    """Runtime configuration for continuation behaviour."""

    enabled: bool = True
    max_continuations: int = 5
    detect_code_truncation: bool = True


def should_continue(response: str, config: ContinuationConfig) -> bool:
    """Return *True* if the engine should attempt a continuation for *response*.

    This is a lightweight check used before invoking the full engine.
    """
    if not config.enabled:
        return False
    if not response or not response.strip():
        return False

    stripped = response.rstrip()
    last_line = stripped.rsplit("\n", 1)[-1].strip()

    # Explicit markers
    simple_markers = ["...", "# continued", "// continued", "/* continued"]
    for marker in simple_markers:
        if last_line.endswith(marker):
            return True

    # Code-block truncation detection
    if config.detect_code_truncation:
        opens = sum(1 for ch in stripped if ch in "({[")
        closes = sum(1 for ch in stripped if ch in ")}]")
        if opens > closes:
            return True

    return False
