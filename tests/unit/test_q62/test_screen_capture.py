"""Tests for ScreenCapture — Q62 Task 422."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestScreenCaptureInterface:
    def test_screen_capture_has_capture_method(self):
        from lidco.multimodal.screen_capture import ScreenCapture
        sc = ScreenCapture()
        assert hasattr(sc, "capture")
        assert hasattr(sc, "capture_region")
        assert hasattr(sc, "capture_window")

    def test_has_pil_flag(self):
        import lidco.multimodal.screen_capture as m
        assert hasattr(m, "_HAS_PIL")


class TestCaptureWithPIL:
    def test_capture_uses_pil_when_available(self, tmp_path):
        from lidco.multimodal.screen_capture import ScreenCapture
        out = tmp_path / "screenshot.png"
        mock_img = MagicMock()
        with patch("lidco.multimodal.screen_capture._HAS_PIL", True):
            with patch("lidco.multimodal.screen_capture.ImageGrab") as mock_grab:
                mock_grab.grab.return_value = mock_img
                sc = ScreenCapture()
                result = sc.capture(output_path=str(out))
        mock_img.save.assert_called_once()
        assert result == out

    def test_capture_region_uses_pil(self, tmp_path):
        from lidco.multimodal.screen_capture import ScreenCapture
        out = tmp_path / "region.png"
        mock_img = MagicMock()
        with patch("lidco.multimodal.screen_capture._HAS_PIL", True):
            with patch("lidco.multimodal.screen_capture.ImageGrab") as mock_grab:
                mock_grab.grab.return_value = mock_img
                sc = ScreenCapture()
                result = sc.capture_region((0, 0, 100, 100), output_path=str(out))
        mock_img.save.assert_called_once()
        assert result == out


class TestCaptureWithoutPIL:
    def test_capture_linux_fallback_with_scrot(self, tmp_path):
        from lidco.multimodal.screen_capture import ScreenCapture
        out = tmp_path / "screen.png"
        with patch("lidco.multimodal.screen_capture._HAS_PIL", False):
            with patch("lidco.multimodal.screen_capture.shutil.which", return_value="/usr/bin/scrot"):
                with patch("lidco.multimodal.screen_capture.subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    sc = ScreenCapture()
                    result = sc.capture(output_path=str(out))
        assert result == out

    def test_capture_raises_without_any_backend(self, tmp_path):
        from lidco.multimodal.screen_capture import ScreenCapture
        out = tmp_path / "screen.png"
        with patch("lidco.multimodal.screen_capture._HAS_PIL", False):
            with patch("lidco.multimodal.screen_capture.shutil.which", return_value=None):
                sc = ScreenCapture()
                with pytest.raises(RuntimeError):
                    sc.capture(output_path=str(out))

    def test_capture_region_raises_without_pil_or_scrot(self):
        from lidco.multimodal.screen_capture import ScreenCapture
        with patch("lidco.multimodal.screen_capture._HAS_PIL", False):
            with patch("lidco.multimodal.screen_capture.shutil.which", return_value=None):
                sc = ScreenCapture()
                with pytest.raises(RuntimeError):
                    sc.capture_region((0, 0, 100, 100))


class TestDefaultOutputPath:
    def test_default_output_path_is_png(self):
        from lidco.multimodal.screen_capture import _default_output_path
        p = _default_output_path()
        assert p.suffix == ".png"
        assert "lidco_capture" in p.name
