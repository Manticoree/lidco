"""Tests for ScreenshotAnalyzer (T573)."""
from __future__ import annotations
import pytest
from lidco.browser.screenshot_analyzer import ScreenshotAnalyzer, VisualIssue, AnalysisResult


def test_analyze_nonexistent_file():
    a = ScreenshotAnalyzer()
    result = a.analyze_file("/nonexistent/file.png")
    assert len(result.issues) > 0
    assert result.issues[0].kind == "file_not_found"


def test_analyze_html_error_text():
    a = ScreenshotAnalyzer()
    result = a.analyze_html_text("<html><body>500 Internal Server Error</body></html>")
    kinds = {i.kind for i in result.issues}
    assert "error_text" in kinds


def test_analyze_html_js_error():
    a = ScreenshotAnalyzer()
    result = a.analyze_html_text("Uncaught TypeError: Cannot read property 'foo' of undefined")
    kinds = {i.kind for i in result.issues}
    assert "js_error" in kinds


def test_analyze_html_clean():
    a = ScreenshotAnalyzer()
    result = a.analyze_html_text("<html><body><p>Hello world</p></body></html>")
    assert len(result.issues) == 0


def test_analyze_b64_tiny_data():
    import base64
    a = ScreenshotAnalyzer()
    a._available = False  # force fallback
    tiny = base64.b64encode(b"\x00" * 10).decode()
    result = a.analyze_b64(tiny)
    assert result.is_blank is True


def test_analyze_b64_invalid():
    a = ScreenshotAnalyzer()
    result = a.analyze_b64("NOT_VALID_BASE64!!!")
    assert len(result.issues) > 0


def test_visual_issue_dataclass():
    issue = VisualIssue(kind="blank_page", severity="high", description="blank")
    assert issue.severity == "high"


def test_format_result_no_issues():
    result = AnalysisResult(issues=[], width=1920, height=1080)
    fmt = result.format()
    assert "No visual issues" in fmt
