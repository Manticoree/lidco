"""Q213 CLI commands: /gen-docstring, /api-ref, /changelog, /find-examples."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q213 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /gen-docstring
    # ------------------------------------------------------------------

    async def gen_docstring_handler(args: str) -> str:
        from lidco.doc_intel.docstring_gen import DocstringGenerator, DocStyle

        parts = args.strip().split(maxsplit=1)
        style_name = parts[0].upper() if parts else "GOOGLE"
        source = parts[1] if len(parts) > 1 else ""
        if not source:
            return "Usage: /gen-docstring [GOOGLE|NUMPY|SPHINX] <function source>"
        try:
            style = DocStyle[style_name]
        except KeyError:
            style = DocStyle.GOOGLE
            source = args.strip()
        gen = DocstringGenerator(style=style)
        try:
            result = gen.generate(source)
        except ValueError as exc:
            return f"Error: {exc}"
        return f"# {result.function_name}\n\n{result.docstring}"

    # ------------------------------------------------------------------
    # /api-ref
    # ------------------------------------------------------------------

    async def api_ref_handler(args: str) -> str:
        from lidco.doc_intel.api_reference import APIReference

        source = args.strip()
        if not source:
            return "Usage: /api-ref <python source>"
        ref = APIReference()
        entries = ref.scan_source(source)
        if not entries:
            return "No API entries found."
        return ref.to_markdown()

    # ------------------------------------------------------------------
    # /changelog
    # ------------------------------------------------------------------

    async def changelog_handler(args: str) -> str:
        from lidco.doc_intel.changelog_auto import ChangelogGenerator

        raw = args.strip()
        if not raw:
            return "Usage: /changelog <commit messages, one per line>"
        messages = [m.strip() for m in raw.splitlines() if m.strip()]
        gen = ChangelogGenerator()
        entries = gen.parse_commits(messages)
        if not entries:
            return "No conventional commits found."
        return gen.generate(entries)

    # ------------------------------------------------------------------
    # /find-examples
    # ------------------------------------------------------------------

    async def find_examples_handler(args: str) -> str:
        from lidco.doc_intel.example_miner import ExampleMiner

        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /find-examples <target_name> <source>"
        target, source = parts
        miner = ExampleMiner()
        examples = miner.find_examples(source, target)
        if not examples:
            return f"No examples found for '{target}'."
        lines = [f"Found {len(examples)} example(s) for '{target}':"]
        for ex in miner.rank_by_clarity(examples):
            lines.append(f"\n--- {ex.function_name} (score={ex.clarity_score:.2f}) ---")
            lines.append(ex.source)
        return "\n".join(lines)

    registry.register(SlashCommand("gen-docstring", "Generate docstring for a function", gen_docstring_handler))
    registry.register(SlashCommand("api-ref", "Generate API reference from source", api_ref_handler))
    registry.register(SlashCommand("changelog", "Generate changelog from commits", changelog_handler))
    registry.register(SlashCommand("find-examples", "Find usage examples in code", find_examples_handler))
