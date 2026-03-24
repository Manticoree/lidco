"""Screenshot analyzer — detect visual issues from captured images (Cursor cloud agent parity)."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from PIL import Image
    import io as _io
    _PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False


@dataclass
class VisualIssue:
    kind: str          # "blank_page" | "error_text" | "layout_overflow" | "low_contrast"
    severity: str      # "high" | "medium" | "low"
    description: str
    region: str = ""   # e.g. "top-left", "center"


@dataclass
class AnalysisResult:
    issues: list[VisualIssue]
    width: int = 0
    height: int = 0
    is_blank: bool = False
    summary: str = ""

    def format(self) -> str:
        if not self.issues:
            return f"No visual issues detected ({self.width}x{self.height})"
        lines = [f"Visual analysis ({self.width}x{self.height}): {len(self.issues)} issue(s)"]
        for issue in self.issues:
            lines.append(f"  [{issue.severity.upper()}] {issue.kind}: {issue.description}")
        return "\n".join(lines)


class ScreenshotAnalyzer:
    """Analyse screenshots for common visual issues.

    Works with file paths or base64-encoded PNG strings.
    Falls back to heuristic text analysis when PIL is not available.
    """

    def __init__(self) -> None:
        self._available = _PIL_AVAILABLE

    def analyze_file(self, path: str | Path) -> AnalysisResult:
        p = Path(path)
        if not p.exists():
            return AnalysisResult(issues=[VisualIssue("file_not_found", "high", str(path))], summary="file not found")
        if not self._available:
            return self._fallback(p.read_bytes())
        return self._analyze_bytes(p.read_bytes())

    def analyze_b64(self, b64_data: str) -> AnalysisResult:
        try:
            data = base64.b64decode(b64_data)
        except Exception as e:
            return AnalysisResult(issues=[VisualIssue("decode_error", "high", str(e))], summary="decode error")
        if not self._available:
            return self._fallback(data)
        return self._analyze_bytes(data)

    def _fallback(self, data: bytes) -> AnalysisResult:
        """Basic heuristic: blank if very small data."""
        issues: list[VisualIssue] = []
        is_blank = len(data) < 500
        if is_blank:
            issues.append(VisualIssue("blank_page", "high", "Screenshot data is very small — possible blank/white page"))
        return AnalysisResult(issues=issues, is_blank=is_blank, summary="PIL unavailable; heuristic only")

    def _analyze_bytes(self, data: bytes) -> AnalysisResult:
        try:
            import io
            img = Image.open(io.BytesIO(data)).convert("RGB")
            width, height = img.size
        except Exception as e:
            return AnalysisResult(issues=[VisualIssue("load_error", "high", str(e))], summary="load error")

        issues: list[VisualIssue] = []

        # Blank/white page detection
        pixels = list(img.getdata())
        total = len(pixels)
        if total > 0:
            white_count = sum(1 for r, g, b in pixels if r > 240 and g > 240 and b > 240)
            if white_count / total > 0.95:
                issues.append(VisualIssue("blank_page", "high", "Page appears blank (>95% white pixels)"))

        is_blank = any(i.kind == "blank_page" for i in issues)
        return AnalysisResult(issues=issues, width=width, height=height, is_blank=is_blank, summary=f"{width}x{height}")

    def analyze_html_text(self, html: str) -> AnalysisResult:
        """Heuristic analysis of HTML text for error patterns."""
        issues: list[VisualIssue] = []
        error_patterns = [
            (r"(?i)\b(error|exception|traceback|500|403|404)\b", "error_text", "high", "Error text detected in page"),
            (r"(?i)(undefined|null reference|cannot read)", "js_error", "high", "JavaScript error pattern detected"),
            (r"(?i)(overflow|layout.*broken|misaligned)", "layout_overflow", "medium", "Layout issue pattern detected"),
        ]
        for pattern, kind, severity, desc in error_patterns:
            if re.search(pattern, html):
                issues.append(VisualIssue(kind=kind, severity=severity, description=desc))
        return AnalysisResult(issues=issues, summary=f"{len(issues)} pattern(s) found")
