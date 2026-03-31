"""Q137 — TextNormalizer: text normalization utilities."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class NormalizeResult:
    """Result of text normalization."""

    original: str
    normalized: str
    changes: list[str] = field(default_factory=list)


class TextNormalizer:
    """Common text normalization operations."""

    def normalize(self, text: str) -> NormalizeResult:
        """Apply full normalization: strip, collapse whitespace, lowercase."""
        changes: list[str] = []
        result = text
        stripped = result.strip()
        if stripped != result:
            changes.append("stripped")
            result = stripped
        collapsed = self.collapse_whitespace(result)
        if collapsed != result:
            changes.append("collapsed_whitespace")
            result = collapsed
        lowered = result.lower()
        if lowered != result:
            changes.append("lowered")
            result = lowered
        return NormalizeResult(original=text, normalized=result, changes=changes)

    def collapse_whitespace(self, text: str) -> str:
        """Collapse runs of whitespace into a single space."""
        return re.sub(r"\s+", " ", text)

    def strip_punctuation(self, text: str) -> str:
        """Remove all punctuation characters."""
        return re.sub(r"[^\w\s]", "", text)

    def to_slug(self, text: str) -> str:
        """Convert to URL-friendly slug: lowercase, hyphens, no special chars."""
        slug = text.lower().strip()
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return slug

    def truncate(self, text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate *text* to *max_length* characters, appending *suffix* if cut."""
        if len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    def remove_html_tags(self, text: str) -> str:
        """Strip HTML tags from *text*."""
        return re.sub(r"<[^>]+>", "", text)
