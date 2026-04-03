"""IconSet — Unicode icon sets; Nerd Fonts; fallback ASCII."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Icon:
    """An immutable icon with unicode and ASCII fallback."""

    name: str
    unicode: str
    ascii_fallback: str
    category: str = "general"


_DEFAULT_ICONS: list[tuple[str, str, str, str]] = [
    ("success", "✓", "[OK]", "status"),
    ("error", "✗", "[ERR]", "status"),
    ("warning", "⚠", "[WARN]", "status"),
    ("info", "ℹ", "[INFO]", "status"),
    ("spinner", "⠋", "[-]", "status"),
    ("folder", "📁", "[DIR]", "filesystem"),
    ("file", "📄", "[FILE]", "filesystem"),
    ("git", "⎇", "[GIT]", "vcs"),
]


class IconSet:
    """Manage icons with unicode/ASCII toggle."""

    def __init__(self, use_unicode: bool = True) -> None:
        self._icons: dict[str, Icon] = {}
        self._use_unicode: bool = use_unicode
        for name, uni, ascii_fb, cat in _DEFAULT_ICONS:
            self._icons[name] = Icon(name=name, unicode=uni, ascii_fallback=ascii_fb, category=cat)

    def get(self, name: str) -> str:
        """Return the icon string (unicode or ascii based on setting)."""
        icon = self._icons.get(name)
        if icon is None:
            return ""
        return icon.unicode if self._use_unicode else icon.ascii_fallback

    def set(self, name: str, unicode: str, ascii_fallback: str, category: str = "general") -> Icon:
        """Add or update an icon."""
        icon = Icon(name=name, unicode=unicode, ascii_fallback=ascii_fallback, category=category)
        self._icons[name] = icon
        return icon

    def remove(self, name: str) -> bool:
        """Remove an icon by name."""
        if name in self._icons:
            del self._icons[name]
            return True
        return False

    def by_category(self, category: str) -> list[Icon]:
        """Return icons in a given category."""
        return [i for i in self._icons.values() if i.category == category]

    def all_icons(self) -> list[Icon]:
        """Return all icons."""
        return list(self._icons.values())

    def toggle_unicode(self, enabled: bool) -> None:
        """Toggle unicode rendering on/off."""
        self._use_unicode = enabled

    def summary(self) -> dict:
        """Return a summary dict."""
        categories: dict[str, int] = {}
        for icon in self._icons.values():
            categories[icon.category] = categories.get(icon.category, 0) + 1
        return {
            "total": len(self._icons),
            "use_unicode": self._use_unicode,
            "categories": categories,
            "names": sorted(self._icons.keys()),
        }
