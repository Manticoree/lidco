"""
Task 1704 — Data Masking

Mask sensitive data: PII detection, consistent replacement, reversible,
format-preserving.
"""

from __future__ import annotations

import hashlib
import re
import string
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class PIIType(str, Enum):
    """Categories of personally identifiable information."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


@dataclass(frozen=True)
class MaskRule:
    """A rule that describes how to detect and mask a PII type."""

    pii_type: PIIType
    pattern: str  # regex
    replacement: str = "***"
    format_preserving: bool = False


@dataclass(frozen=True)
class MaskResult:
    """Result of masking a single value."""

    original_hash: str
    masked_value: str
    pii_type: PIIType
    reversible: bool = False


@dataclass(frozen=True)
class MaskReport:
    """Aggregate masking report."""

    total_fields: int = 0
    masked_fields: int = 0
    pii_types_found: tuple[str, ...] = ()
    results: tuple[MaskResult, ...] = ()


# ---------------------------------------------------------------------------
# Built-in patterns
# ---------------------------------------------------------------------------

_BUILTIN_RULES: tuple[MaskRule, ...] = (
    MaskRule(
        pii_type=PIIType.EMAIL,
        pattern=r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        replacement="masked@example.com",
        format_preserving=True,
    ),
    MaskRule(
        pii_type=PIIType.PHONE,
        pattern=r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        replacement="000-000-0000",
        format_preserving=True,
    ),
    MaskRule(
        pii_type=PIIType.SSN,
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        replacement="000-00-0000",
        format_preserving=True,
    ),
    MaskRule(
        pii_type=PIIType.CREDIT_CARD,
        pattern=r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        replacement="0000-0000-0000-0000",
        format_preserving=True,
    ),
    MaskRule(
        pii_type=PIIType.IP_ADDRESS,
        pattern=r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        replacement="0.0.0.0",
        format_preserving=True,
    ),
)


# ---------------------------------------------------------------------------
# DataMasker
# ---------------------------------------------------------------------------

class DataMasker:
    """
    Mask sensitive / PII data in strings or dictionaries.

    Supports consistent (deterministic) replacement, format-preserving masks,
    and optional reversibility via a lookup table.

    Usage::

        masker = DataMasker()
        masked_text = masker.mask_string("Contact alice@test.com")
        report = masker.mask_dict({"email": "bob@test.com", "age": 30})
    """

    def __init__(
        self,
        *,
        rules: Optional[Sequence[MaskRule]] = None,
        consistent: bool = True,
        reversible: bool = False,
        seed: str = "lidco",
    ) -> None:
        self._rules: tuple[MaskRule, ...] = tuple(rules) if rules is not None else _BUILTIN_RULES
        self._consistent = consistent
        self._reversible = reversible
        self._seed = seed
        # mapping original→masked for consistency & reversibility
        self._map: Dict[str, str] = {}
        self._reverse_map: Dict[str, str] = {}

    # -- public API ----------------------------------------------------------

    @property
    def rules(self) -> tuple[MaskRule, ...]:
        return self._rules

    def add_rule(self, rule: MaskRule) -> DataMasker:
        """Return a new masker with an additional rule."""
        new_rules = (*self._rules, rule)
        m = DataMasker.__new__(DataMasker)
        m._rules = new_rules
        m._consistent = self._consistent
        m._reversible = self._reversible
        m._seed = self._seed
        m._map = dict(self._map)
        m._reverse_map = dict(self._reverse_map)
        return m

    def mask_string(self, text: str) -> str:
        """Mask all PII occurrences in *text*."""
        result = text
        for rule in self._rules:
            result = re.sub(rule.pattern, lambda m: self._replace(m.group(), rule), result)
        return result

    def mask_dict(self, data: Dict[str, Any]) -> MaskReport:
        """Mask PII in dict values (shallow, string values only)."""
        results: list[MaskResult] = []
        pii_found: set[str] = set()
        masked_count = 0

        for key, value in data.items():
            if not isinstance(value, str):
                continue
            new_val = value
            field_masked = False
            for rule in self._rules:
                match = re.search(rule.pattern, new_val)
                if match:
                    new_val = re.sub(
                        rule.pattern,
                        lambda m, r=rule: self._replace(m.group(), r),
                        new_val,
                    )
                    pii_found.add(rule.pii_type.value)
                    field_masked = True
                    results.append(MaskResult(
                        original_hash=self._hash(value),
                        masked_value=new_val,
                        pii_type=rule.pii_type,
                        reversible=self._reversible,
                    ))
            if field_masked:
                masked_count += 1

        return MaskReport(
            total_fields=len(data),
            masked_fields=masked_count,
            pii_types_found=tuple(sorted(pii_found)),
            results=tuple(results),
        )

    def detect_pii(self, text: str) -> list[PIIType]:
        """Return list of PII types detected in *text*."""
        found: list[PIIType] = []
        for rule in self._rules:
            if re.search(rule.pattern, text):
                found.append(rule.pii_type)
        return found

    def unmask(self, masked_text: str) -> str:
        """Reverse masking if reversible mode was enabled."""
        if not self._reversible:
            raise RuntimeError("Masker is not in reversible mode")
        result = masked_text
        for masked_val, original_val in self._reverse_map.items():
            result = result.replace(masked_val, original_val)
        return result

    # -- private helpers -----------------------------------------------------

    def _replace(self, original: str, rule: MaskRule) -> str:
        if self._consistent and original in self._map:
            return self._map[original]

        if rule.format_preserving:
            replacement = self._format_preserving_mask(original, rule)
        else:
            replacement = rule.replacement

        if self._consistent:
            self._map[original] = replacement

        if self._reversible:
            self._reverse_map[replacement] = original

        return replacement

    def _format_preserving_mask(self, original: str, rule: MaskRule) -> str:
        """Generate a deterministic, format-preserving replacement."""
        h = hashlib.sha256(f"{self._seed}:{original}".encode()).hexdigest()

        if rule.pii_type == PIIType.EMAIL:
            local_len = original.index("@") if "@" in original else 5
            local = h[:local_len]
            return f"{local}@masked.example.com"

        if rule.pii_type == PIIType.PHONE:
            digits = "".join(c for c in h if c.isdigit())[:10]
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:10]}"

        if rule.pii_type == PIIType.SSN:
            digits = "".join(c for c in h if c.isdigit())[:9]
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:9]}"

        if rule.pii_type == PIIType.CREDIT_CARD:
            digits = "".join(c for c in h if c.isdigit())[:16]
            return f"{digits[:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"

        if rule.pii_type == PIIType.IP_ADDRESS:
            parts = [str(int(h[i * 2: i * 2 + 2], 16) % 256) for i in range(4)]
            return ".".join(parts)

        return rule.replacement

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:16]
