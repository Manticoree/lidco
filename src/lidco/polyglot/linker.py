"""Cross-language symbol linker — finds references between languages."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.polyglot.parser import Symbol


@dataclass(frozen=True)
class Link:
    """A link between two symbols across languages."""

    source: Symbol
    target: Symbol
    link_type: str


class CrossLanguageLinker:
    """Find links between symbols from different languages."""

    def __init__(self) -> None:
        self._symbols: list[Symbol] = []

    def add_symbols(self, symbols: list[Symbol]) -> None:
        """Add symbols to the linker (immutable append)."""
        self._symbols = [*self._symbols, *symbols]

    def find_links(self) -> list[Link]:
        """Match symbols by name across languages."""
        by_name: dict[str, list[Symbol]] = {}
        for sym in self._symbols:
            by_name.setdefault(sym.name, []).append(sym)

        links: list[Link] = []
        seen: set[tuple[str, str, str, str]] = set()
        for name, group in by_name.items():
            if len(group) < 2:
                continue
            for i, src in enumerate(group):
                for tgt in group[i + 1 :]:
                    if src.language == tgt.language:
                        continue
                    key = (src.name, src.language, tgt.name, tgt.language)
                    if key not in seen:
                        seen.add(key)
                        links.append(Link(source=src, target=tgt, link_type="name_match"))
        return links

    def find_api_boundaries(self) -> list[Link]:
        """Identify API endpoints referenced across languages."""
        api_kinds = {"function", "method", "class"}
        api_symbols = [s for s in self._symbols if s.kind in api_kinds]

        by_name: dict[str, list[Symbol]] = {}
        for sym in api_symbols:
            by_name.setdefault(sym.name, []).append(sym)

        links: list[Link] = []
        seen: set[tuple[str, str, str, str]] = set()
        for name, group in by_name.items():
            if len(group) < 2:
                continue
            langs = {s.language for s in group}
            if len(langs) < 2:
                continue
            for i, src in enumerate(group):
                for tgt in group[i + 1 :]:
                    if src.language == tgt.language:
                        continue
                    key = (src.name, src.language, tgt.name, tgt.language)
                    if key not in seen:
                        seen.add(key)
                        links.append(Link(source=src, target=tgt, link_type="api_boundary"))
        return links

    def summary(self) -> str:
        """Return a human-readable summary of cross-language links."""
        links = self.find_links()
        if not links:
            return "No cross-language links found."
        langs: set[str] = set()
        for link in links:
            langs.add(link.source.language)
            langs.add(link.target.language)
        lines = [
            f"{len(links)} cross-language link(s) across {len(langs)} language(s):",
        ]
        for link in links:
            lines.append(
                f"  {link.source.language}:{link.source.name} <-> "
                f"{link.target.language}:{link.target.name} [{link.link_type}]"
            )
        return "\n".join(lines)
