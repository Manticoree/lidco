"""Watermark engine — embed / detect invisible provenance markers in code."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

# Zero-width characters used for embedding.
_ZW_SPACE = "\u200b"  # zero-width space  (bit 0)
_ZW_NON_JOINER = "\u200c"  # zero-width non-joiner (bit 1)
_ZW_JOINER = "\u200d"  # zero-width joiner (delimiter only)
_MARKER_START = _ZW_JOINER + _ZW_JOINER + _ZW_JOINER
_MARKER_END = _ZW_JOINER + _ZW_JOINER + _ZW_JOINER + _ZW_JOINER


@dataclass(frozen=True)
class Watermark:
    """Embedded watermark metadata."""

    id: str
    source: str
    timestamp: float
    signature: str


class WatermarkEngine:
    """Embed / detect invisible watermarks in code strings."""

    def __init__(self, secret: str = "lidco-wm") -> None:
        self._secret = secret
        self._embedded = 0
        self._detected = 0

    # ------------------------------------------------------------------

    def create_signature(self, source: str, timestamp: float) -> str:
        """HMAC-SHA256 signature for provenance."""
        msg = f"{source}:{timestamp}".encode()
        return hmac.new(self._secret.encode(), msg, hashlib.sha256).hexdigest()[:16]

    def embed(self, code: str, source: str = "lidco") -> tuple[str, Watermark]:
        """Embed an invisible watermark and return (watermarked_code, watermark)."""
        ts = time.time()
        wm_id = uuid.uuid4().hex[:12]
        sig = self.create_signature(source, ts)
        payload = json.dumps({"id": wm_id, "s": source, "t": ts, "sig": sig})
        encoded = self._encode_payload(payload)
        watermarked = code + _MARKER_START + encoded + _MARKER_END
        self._embedded += 1
        return watermarked, Watermark(id=wm_id, source=source, timestamp=ts, signature=sig)

    def detect(self, code: str) -> Watermark | None:
        """Extract watermark if present."""
        start = code.find(_MARKER_START)
        end = code.find(_MARKER_END, start + len(_MARKER_START)) if start != -1 else -1
        if start == -1 or end == -1:
            return None
        encoded = code[start + len(_MARKER_START): end]
        try:
            payload = json.loads(self._decode_payload(encoded))
        except (json.JSONDecodeError, ValueError):
            return None
        self._detected += 1
        return Watermark(
            id=payload["id"],
            source=payload["s"],
            timestamp=payload["t"],
            signature=payload["sig"],
        )

    def verify(self, code: str, watermark: Watermark) -> bool:
        """Verify that *watermark* matches content in *code*."""
        detected = self.detect(code)
        if detected is None:
            return False
        expected_sig = self.create_signature(watermark.source, watermark.timestamp)
        return detected.signature == expected_sig and detected.id == watermark.id

    def strip(self, code: str) -> str:
        """Remove watermark from *code*."""
        start = code.find(_MARKER_START)
        end = code.find(_MARKER_END, start + len(_MARKER_START)) if start != -1 else -1
        if start == -1 or end == -1:
            return code
        return code[:start] + code[end + len(_MARKER_END):]

    def summary(self) -> dict:
        return {
            "embedded": self._embedded,
            "detected": self._detected,
        }

    # ------------------------------------------------------------------
    # Internal encoding: convert each char to zero-width binary sequence.
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_payload(text: str) -> str:
        bits: list[str] = []
        for ch in text:
            for bit in format(ord(ch), "08b"):
                bits.append(_ZW_SPACE if bit == "0" else _ZW_NON_JOINER)
        return "".join(bits)

    @staticmethod
    def _decode_payload(encoded: str) -> str:
        chars: list[str] = []
        bits: list[str] = []
        for ch in encoded:
            if ch == _ZW_SPACE:
                bits.append("0")
            elif ch == _ZW_NON_JOINER:
                bits.append("1")
            else:
                continue
            if len(bits) == 8:
                chars.append(chr(int("".join(bits), 2)))
                bits = []
        return "".join(chars)
