"""Image / screenshot analysis via vision-capable LLMs."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Models known to support vision
_VISION_MODELS = [
    "anthropic/claude-3-haiku-20240307",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-opus-20240229",
    "openai/gpt-4o",
    "openai/gpt-4-vision-preview",
    "openai/gpt-4o-mini",
]


def _model_supports_vision(model: str) -> bool:
    """Heuristic: return True if *model* likely supports vision."""
    model_lower = model.lower()
    vision_keywords = ("vision", "4o", "claude-3", "claude-3-5", "gemini", "gpt-4v")
    return any(kw in model_lower for kw in vision_keywords)


def _pick_vision_model(current_model: str) -> str:
    """Return *current_model* if it supports vision, else fall back."""
    if _model_supports_vision(current_model):
        return current_model
    return _VISION_MODELS[0]  # fallback: claude-3-haiku


def _encode_image(path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for *path*."""
    ext = path.suffix.lower()
    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_map.get(ext, "image/png")
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return data, media_type


class ImageAnalyzer:
    """Analyze images using a vision-capable LLM."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def _get_model(self) -> str:
        try:
            current = self._session.config.llm.default_model
        except Exception:
            current = ""
        return _pick_vision_model(current)

    async def analyze(
        self, image_path: str | Path, question: str = "Describe this image"
    ) -> str:
        """Analyze *image_path* with the given *question*.

        Returns the LLM's textual description / analysis.
        """
        path = Path(image_path)
        if not path.exists():
            return f"Error: file not found: {path}"

        ext = path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return (
                f"Unsupported image format: {ext}. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        b64_data, media_type = _encode_image(path)
        model = self._get_model()

        # Build a vision message using the litellm / openai multimodal format
        vision_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64_data}"
                    },
                },
                {"type": "text", "text": question},
            ],
        }

        try:
            import litellm  # type: ignore[import]

            response = await litellm.acompletion(
                model=model,
                messages=[vision_message],
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""
        except ImportError:
            return (
                "litellm is required for image analysis. "
                "Install it with: pip install litellm"
            )
        except Exception as exc:
            return f"Image analysis failed: {exc}"
