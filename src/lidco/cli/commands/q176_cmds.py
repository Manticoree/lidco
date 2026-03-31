"""CLI commands for Q176 — Input Preprocessing & Context Enrichment."""
from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q176_commands(registry) -> None:
    from lidco.input.intent_classifier import IntentClassifier
    from lidco.input.prompt_rewriter import PromptRewriter
    from lidco.input.auto_attach import AutoAttachResolver
    from lidco.input.context_compressor import ContextCompressor

    async def classify_handler(args: str) -> str:
        if not args.strip():
            return "Usage: /classify <prompt>\nClassifies the intent of a prompt (edit, ask, debug, generate, refactor, explain)."
        classifier = IntentClassifier()
        result = classifier.classify(args.strip())
        lines = [
            f"Intent: {result.intent.value}",
            f"Confidence: {result.confidence:.0%}",
        ]
        if result.suggested_command:
            lines.append(f"Suggested command: {result.suggested_command}")
        # Show all matches
        all_results = classifier.classify_all(args.strip())
        if len(all_results) > 1:
            lines.append("\nAll matches:")
            for r in all_results:
                lines.append(f"  {r.intent.value}: {r.confidence:.0%}")
        return "\n".join(lines)

    async def rewrite_handler(args: str) -> str:
        if not args.strip():
            return "Usage: /rewrite <prompt>\nExpands vague prompts with available context."
        rewriter = PromptRewriter()
        result = rewriter.rewrite(args.strip())
        if result.was_rewritten:
            return f"Original: {result.original}\nRewritten: {result.rewritten}\nExpansions: {', '.join(result.expansions)}"
        return f"Prompt is already specific: {result.original}"

    async def auto_attach_handler(args: str) -> str:
        if not args.strip():
            return "Usage: /auto-attach <prompt>\nFinds implicitly referenced files in a prompt."
        resolver = AutoAttachResolver()
        # In real usage, project_files would come from the session
        result = resolver.resolve(args.strip(), [])
        if not result:
            return "No implicit file references found in the prompt."
        lines = ["Suggested attachments:"]
        for r in result:
            lines.append(f"  {r.path} (score: {r.score:.0%}, reason: {r.reason})")
        return "\n".join(lines)

    async def compress_context_handler(args: str) -> str:
        if not args.strip():
            return "Usage: /compress-context <code>\nCompresses code by keeping signatures and dropping bodies."
        compressor = ContextCompressor()
        result = compressor.compress(args.strip())
        lines = [
            f"Original lines: {result.original_lines}",
            f"Compressed lines: {result.compressed_lines}",
            f"Ratio: {result.ratio:.0%}",
            "",
            result.content,
        ]
        return "\n".join(lines)

    registry.register(SlashCommand("classify", "Classify prompt intent", classify_handler))
    registry.register(SlashCommand("rewrite", "Expand vague prompts with context", rewrite_handler))
    registry.register(SlashCommand("auto-attach", "Find implicit file references", auto_attach_handler))
    registry.register(SlashCommand("compress-context", "Compress code keeping signatures", compress_context_handler))
