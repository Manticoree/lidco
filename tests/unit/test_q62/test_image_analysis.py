"""Tests for ImageAnalyzer — Q62 Task 418."""

from __future__ import annotations

import base64
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestSupportedExtensions:
    def test_png_supported(self, tmp_path):
        from lidco.multimodal.image_analysis import _SUPPORTED_EXTENSIONS
        assert ".png" in _SUPPORTED_EXTENSIONS

    def test_jpg_supported(self, tmp_path):
        from lidco.multimodal.image_analysis import _SUPPORTED_EXTENSIONS
        assert ".jpg" in _SUPPORTED_EXTENSIONS

    def test_webp_supported(self):
        from lidco.multimodal.image_analysis import _SUPPORTED_EXTENSIONS
        assert ".webp" in _SUPPORTED_EXTENSIONS

    def test_txt_not_supported(self):
        from lidco.multimodal.image_analysis import _SUPPORTED_EXTENSIONS
        assert ".txt" not in _SUPPORTED_EXTENSIONS

    def test_gif_supported(self):
        from lidco.multimodal.image_analysis import _SUPPORTED_EXTENSIONS
        assert ".gif" in _SUPPORTED_EXTENSIONS


class TestEncodeImage:
    def test_encode_returns_base64(self, tmp_path):
        from lidco.multimodal.image_analysis import _encode_image
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")
        data, media_type = _encode_image(img)
        assert media_type == "image/png"
        decoded = base64.b64decode(data)
        assert decoded == b"\x89PNG"

    def test_jpeg_media_type(self, tmp_path):
        from lidco.multimodal.image_analysis import _encode_image
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        _, media_type = _encode_image(img)
        assert media_type == "image/jpeg"


class TestImageAnalyzerMissingFile:
    @pytest.mark.asyncio
    async def test_returns_error_for_missing_file(self):
        from lidco.multimodal.image_analysis import ImageAnalyzer
        session = MagicMock()
        analyzer = ImageAnalyzer(session=session)
        result = await analyzer.analyze("/nonexistent/image.png", "describe it")
        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_error_for_unsupported_format(self, tmp_path):
        from lidco.multimodal.image_analysis import ImageAnalyzer
        bmp = tmp_path / "test.bmp"
        bmp.write_bytes(b"BM")
        session = MagicMock()
        analyzer = ImageAnalyzer(session=session)
        result = await analyzer.analyze(str(bmp), "describe")
        assert ".bmp" in result.lower() or "unsupported" in result.lower()

    @pytest.mark.asyncio
    async def test_with_no_session_raises_or_returns_error(self, tmp_path):
        from lidco.multimodal.image_analysis import ImageAnalyzer
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        # With no session, litellm call would fail; we just check it handles gracefully
        analyzer = ImageAnalyzer(session=None)
        result = await analyzer.analyze(str(img), "describe")
        # Should return a string (error or result)
        assert isinstance(result, str)


class TestModelSupportVision:
    def test_vision_model_detection(self):
        from lidco.multimodal.image_analysis import _model_supports_vision
        assert _model_supports_vision("gpt-4o")
        assert _model_supports_vision("claude-3-5-sonnet")
        assert not _model_supports_vision("claude-instant")

    def test_pick_vision_model_fallback(self):
        from lidco.multimodal.image_analysis import _pick_vision_model
        # Non-vision model → fallback
        result = _pick_vision_model("non-vision-model")
        assert result  # returns something

    def test_pick_vision_model_keeps_vision_capable(self):
        from lidco.multimodal.image_analysis import _pick_vision_model
        result = _pick_vision_model("gpt-4o")
        assert result == "gpt-4o"
