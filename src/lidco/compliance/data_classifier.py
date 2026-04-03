"""Data sensitivity classifier with PII detection and auto-labeling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Sensitivity levels
# ---------------------------------------------------------------------------

class SensitivityLevel:
    """Constants for data sensitivity levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


_LEVEL_ORDER = {
    SensitivityLevel.PUBLIC: 0,
    SensitivityLevel.INTERNAL: 1,
    SensitivityLevel.CONFIDENTIAL: 2,
    SensitivityLevel.RESTRICTED: 3,
}


@dataclass(frozen=True)
class ClassificationResult:
    """Result of data classification."""

    level: str
    confidence: float
    reasons: list[str]
    pii_found: list[str]


# ---------------------------------------------------------------------------
# Built-in PII patterns
# ---------------------------------------------------------------------------

_BUILTIN_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "api_key": r"(?:api[_-]?key|token|secret)[\"':\s=]+[A-Za-z0-9_\-]{16,}",
}

# Mapping from PII type to sensitivity level
_PII_SENSITIVITY: dict[str, str] = {
    "email": SensitivityLevel.CONFIDENTIAL,
    "phone": SensitivityLevel.CONFIDENTIAL,
    "ssn": SensitivityLevel.RESTRICTED,
    "credit_card": SensitivityLevel.RESTRICTED,
    "ip_address": SensitivityLevel.INTERNAL,
    "api_key": SensitivityLevel.RESTRICTED,
}

# Filename hints
_FILENAME_HINTS: dict[str, str] = {
    ".env": SensitivityLevel.RESTRICTED,
    ".pem": SensitivityLevel.RESTRICTED,
    ".key": SensitivityLevel.RESTRICTED,
    "credentials": SensitivityLevel.RESTRICTED,
    "secret": SensitivityLevel.RESTRICTED,
    "password": SensitivityLevel.RESTRICTED,
    "config": SensitivityLevel.INTERNAL,
}


class DataClassifier:
    """Classify data sensitivity and detect PII."""

    def __init__(self, custom_patterns: dict[str, str] | None = None) -> None:
        self._patterns: dict[str, re.Pattern[str]] = {}
        for name, pat in _BUILTIN_PATTERNS.items():
            self._patterns[name] = re.compile(pat)
        if custom_patterns:
            for name, pat in custom_patterns.items():
                self._patterns[name] = re.compile(pat)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> ClassificationResult:
        """Classify text sensitivity based on PII content."""
        detections = self.detect_pii(text)
        if not detections:
            return ClassificationResult(
                level=SensitivityLevel.PUBLIC,
                confidence=1.0,
                reasons=["No PII detected"],
                pii_found=[],
            )

        pii_types = sorted({d["type"] for d in detections})
        max_level = SensitivityLevel.PUBLIC
        reasons: list[str] = []
        for pii_type in pii_types:
            lvl = _PII_SENSITIVITY.get(pii_type, SensitivityLevel.CONFIDENTIAL)
            reasons.append(f"Found {pii_type}")
            if _LEVEL_ORDER.get(lvl, 0) > _LEVEL_ORDER.get(max_level, 0):
                max_level = lvl

        confidence = min(1.0, 0.5 + len(detections) * 0.1)
        return ClassificationResult(
            level=max_level,
            confidence=round(confidence, 2),
            reasons=reasons,
            pii_found=pii_types,
        )

    def detect_pii(self, text: str) -> list[dict]:
        """Return list of PII detections: {type, match, position}."""
        results: list[dict] = []
        for name, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                results.append({
                    "type": name,
                    "match": m.group(),
                    "position": m.start(),
                })
        results.sort(key=lambda d: d["position"])
        return results

    def classify_file(self, content: str, filename: str = "") -> ClassificationResult:
        """Classify file content with filename hints."""
        base_result = self.classify(content)
        if not filename:
            return base_result

        fn_lower = filename.lower()
        hint_level = SensitivityLevel.PUBLIC
        hint_reasons: list[str] = []
        for hint, lvl in _FILENAME_HINTS.items():
            if hint in fn_lower:
                hint_reasons.append(f"Filename contains '{hint}'")
                if _LEVEL_ORDER.get(lvl, 0) > _LEVEL_ORDER.get(hint_level, 0):
                    hint_level = lvl

        if _LEVEL_ORDER.get(hint_level, 0) > _LEVEL_ORDER.get(base_result.level, 0):
            return ClassificationResult(
                level=hint_level,
                confidence=max(base_result.confidence, 0.8),
                reasons=base_result.reasons + hint_reasons,
                pii_found=base_result.pii_found,
            )
        return base_result

    def add_pattern(self, name: str, pattern: str) -> None:
        """Add or replace a detection pattern."""
        self._patterns[name] = re.compile(pattern)
        if name not in _PII_SENSITIVITY:
            _PII_SENSITIVITY[name] = SensitivityLevel.CONFIDENTIAL

    def summary(self) -> dict:
        """Return summary of classifier configuration."""
        return {
            "pattern_count": len(self._patterns),
            "patterns": sorted(self._patterns.keys()),
        }
