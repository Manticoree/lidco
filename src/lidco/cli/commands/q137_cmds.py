"""Q137 CLI commands: /text."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q137 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def text_handler(args: str) -> str:
        from lidco.text.fuzzy_matcher import FuzzyMatcher
        from lidco.text.diff_highlighter import TextDiffHighlighter
        from lidco.text.similarity import SimilarityMetrics
        from lidco.text.normalizer import TextNormalizer

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "match":
            sub_parts = rest.split(maxsplit=1)
            if len(sub_parts) < 2:
                return "Usage: /text match <query> <candidates_csv>"
            query = sub_parts[0]
            candidates = [c.strip() for c in sub_parts[1].split(",")]
            matcher = FuzzyMatcher(candidates)
            results = matcher.match(query)
            if not results:
                return "No matches above threshold."
            lines = [f"Matches for '{query}':"]
            for r in results:
                lines.append(f"  {r.candidate} (score={r.score:.3f})")
            return "\n".join(lines)

        if sub == "diff":
            sub_parts = rest.split("|||")
            if len(sub_parts) < 2:
                return "Usage: /text diff <old>|||<new>"
            hl = TextDiffHighlighter()
            segs = hl.highlight(sub_parts[0].strip(), sub_parts[1].strip())
            return hl.format_inline(segs)

        if sub == "similar":
            sub_parts = rest.split("|||")
            if len(sub_parts) < 2:
                return "Usage: /text similar <a>|||<b>"
            result = SimilarityMetrics.compare(
                sub_parts[0].strip(), sub_parts[1].strip()
            )
            return json.dumps(result, indent=2)

        if sub == "normalize":
            if not rest:
                return "Usage: /text normalize <text>"
            norm = TextNormalizer()
            result = norm.normalize(rest)
            return f"Normalized: {result.normalized!r}\nChanges: {result.changes}"

        return (
            "Usage: /text <sub>\n"
            "  match <query> <candidates_csv>  -- fuzzy match\n"
            "  diff <old>|||<new>              -- inline diff\n"
            "  similar <a>|||<b>               -- similarity metrics\n"
            "  normalize <text>                -- text normalization"
        )

    registry.register(SlashCommand("text", "Text processing & string utilities (Q137)", text_handler))
