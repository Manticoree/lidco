"""Screen capture integration — PIL.ImageGrab (Win/macOS) or scrot/import (Linux)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from PIL import ImageGrab  # type: ignore[import]
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False
    ImageGrab = None  # type: ignore[assignment]

_PLATFORM = sys.platform


def _default_output_path() -> Path:
    ts = int(time.time())
    tmp = Path(tempfile.gettempdir())
    return tmp / f"lidco_capture_{ts}.png"


class ScreenCapture:
    """Capture screenshots using PIL or system tools."""

    def capture(self, output_path: str | Path | None = None) -> Path:
        """Capture the full screen, save to *output_path*, return the path."""
        out = Path(output_path) if output_path else _default_output_path()
        out.parent.mkdir(parents=True, exist_ok=True)

        if _HAS_PIL:
            img = ImageGrab.grab()
            img.save(str(out))
            return out

        # Linux fallback
        return self._capture_linux(out)

    def capture_region(self, bbox: tuple[int, int, int, int], output_path: str | Path | None = None) -> Path:
        """Capture a region (x, y, w, h) of the screen."""
        out = Path(output_path) if output_path else _default_output_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        x, y, w, h = bbox

        if _HAS_PIL:
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(str(out))
            return out

        # Linux: use scrot with geometry
        if shutil.which("scrot"):
            subprocess.run(
                ["scrot", "-a", f"{x},{y},{w},{h}", str(out)],
                check=True,
                timeout=10,
            )
            return out

        raise RuntimeError(
            "No screen capture backend available for region capture. "
            "Install Pillow (pip install Pillow) or scrot (apt install scrot)."
        )

    def capture_window(self, title: str, output_path: str | Path | None = None) -> Path:
        """Capture a window identified by *title* (best-effort)."""
        out = Path(output_path) if output_path else _default_output_path()
        out.parent.mkdir(parents=True, exist_ok=True)

        if _PLATFORM == "win32" and _HAS_PIL:
            # On Windows, try to grab full screen as fallback
            img = ImageGrab.grab()
            img.save(str(out))
            return out

        if _PLATFORM.startswith("linux"):
            # Use import (ImageMagick) with window selection
            if shutil.which("import"):
                try:
                    subprocess.run(
                        ["import", "-window", title, str(out)],
                        check=True,
                        timeout=10,
                    )
                    return out
                except subprocess.CalledProcessError:
                    pass

            # Fallback: full screen capture
            return self._capture_linux(out)

        # macOS: screencapture
        if _PLATFORM == "darwin":
            subprocess.run(
                ["screencapture", "-x", str(out)],
                check=True,
                timeout=10,
            )
            return out

        raise RuntimeError(
            f"Window capture not supported on platform: {_PLATFORM}. "
            "Install Pillow for basic full-screen capture."
        )

    @staticmethod
    def _capture_linux(out: Path) -> Path:
        """Attempt Linux screenshot via scrot or import."""
        if shutil.which("scrot"):
            subprocess.run(["scrot", str(out)], check=True, timeout=10)
            return out
        if shutil.which("import"):
            subprocess.run(["import", "-window", "root", str(out)], check=True, timeout=10)
            return out
        raise RuntimeError(
            "No screen capture backend found. Install one of:\n"
            "  pip install Pillow          (Windows/macOS/Linux)\n"
            "  apt install scrot           (Linux, scrot)\n"
            "  apt install imagemagick     (Linux, import)"
        )


class ScreenCaptureAndAnalyze:
    """Capture a screenshot and pass it to ImageAnalyzer."""

    def __init__(self, session: Any) -> None:
        self._capture = ScreenCapture()
        self._session = session

    async def capture_and_analyze(
        self,
        output_path: str | Path | None = None,
        question: str = "Describe this screenshot",
        bbox: tuple[int, int, int, int] | None = None,
    ) -> tuple[Path, str]:
        """Capture and analyze.

        Returns (saved_path, analysis_text).
        """
        from lidco.multimodal.image_analysis import ImageAnalyzer

        if bbox is not None:
            saved = self._capture.capture_region(bbox, output_path=output_path)
        else:
            saved = self._capture.capture(output_path=output_path)

        analyzer = ImageAnalyzer(self._session)
        analysis = await analyzer.analyze(saved, question=question)
        return saved, analysis
