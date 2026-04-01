"""Q196 CLI commands: /agent-summary, /magic-docs, /readme-gen, /doc-sync."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q196 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    _state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /agent-summary
    # ------------------------------------------------------------------

    async def agent_summary_handler(args: str) -> str:
        from lidco.agents.summarizer import AgentSummarizer

        summarizer: AgentSummarizer | None = _state.get("summarizer")  # type: ignore[assignment]
        if summarizer is None:
            name = args.strip() or "agent"
            summarizer = AgentSummarizer(agent_name=name)
            _state["summarizer"] = summarizer
            return f"Summarizer initialized for '{name}'"
        return summarizer.format_markdown()

    # ------------------------------------------------------------------
    # /magic-docs
    # ------------------------------------------------------------------

    async def magic_docs_handler(args: str) -> str:
        from lidco.docgen.magic_docs import MagicDocsGenerator

        path = args.strip()
        if not path:
            return "Usage: /magic-docs <source_path>"
        gen = MagicDocsGenerator()
        sections = gen.generate(path)
        if not sections:
            return f"No documentation generated for '{path}'."
        return gen.format_markdown(sections)

    # ------------------------------------------------------------------
    # /readme-gen
    # ------------------------------------------------------------------

    async def readme_gen_handler(args: str) -> str:
        from lidco.docgen.readme_gen import READMEConfig, READMEGenerator

        parts = args.strip().split(maxsplit=1)
        project_path = parts[0] if parts else "."
        name = parts[1] if len(parts) > 1 else "MyProject"
        config = READMEConfig(
            project_name=name,
            description=f"Auto-generated README for {name}",
            include_badges=True,
            include_install=True,
        )
        gen = READMEGenerator(config)
        return gen.generate(project_path)

    # ------------------------------------------------------------------
    # /doc-sync
    # ------------------------------------------------------------------

    async def doc_sync_handler(args: str) -> str:
        from lidco.docgen.doc_sync import DocSyncEngine

        project_path = args.strip() or "."
        engine = DocSyncEngine(project_path)
        status = engine.check_staleness()
        if status.total_docs == 0:
            return "No documentation files found."
        lines = [
            f"Total docs: {status.total_docs} | Fresh: {status.fresh} | Stale: {status.stale}"
        ]
        for sd in status.stale_docs:
            lines.append(f"  STALE: {sd.path} — {sd.reason}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("agent-summary", "Show agent action summary", agent_summary_handler))
    registry.register(SlashCommand("magic-docs", "Auto-generate docs from source", magic_docs_handler))
    registry.register(SlashCommand("readme-gen", "Generate README from project", readme_gen_handler))
    registry.register(SlashCommand("doc-sync", "Check documentation freshness", doc_sync_handler))
