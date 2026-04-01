"""Q212 CLI commands: /detect-refactor, /extract, /rename-symbol, /inline."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q212 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /detect-refactor
    # ------------------------------------------------------------------

    async def detect_refactor_handler(args: str) -> str:
        import os
        from lidco.smart_refactor.detector import RefactoringDetector

        path = args.strip()
        if not path:
            return "Usage: /detect-refactor <file>"
        if not os.path.isfile(path):
            return f"File not found: {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        detector = RefactoringDetector()
        opps = detector.detect_all(source, file=path)
        if not opps:
            return "No refactoring opportunities detected."
        lines = [detector.summary(opps), ""]
        for opp in opps:
            lines.append(
                f"  [{opp.smell.value}] {opp.name} (line {opp.line}, "
                f"confidence {opp.confidence:.0%}): {opp.suggestion}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /extract
    # ------------------------------------------------------------------

    async def extract_handler(args: str) -> str:
        from lidco.smart_refactor.extract_engine import ExtractEngine

        parts = args.strip().split()
        if len(parts) < 4:
            return "Usage: /extract <file> <start_line> <end_line> <name>"

        import os

        path, start_s, end_s, name = parts[0], parts[1], parts[2], parts[3]
        if not os.path.isfile(path):
            return f"File not found: {path}"
        try:
            start, end = int(start_s), int(end_s)
        except ValueError:
            return "start_line and end_line must be integers."

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        engine = ExtractEngine()
        result = engine.extract_method(source, start, end, name)
        if not result.success:
            return f"Extraction failed: {result.error}"
        return engine.preview(result)

    # ------------------------------------------------------------------
    # /rename-symbol
    # ------------------------------------------------------------------

    async def rename_symbol_handler(args: str) -> str:
        from lidco.smart_refactor.rename_propagator import RenamePropagator

        parts = args.strip().split()
        if len(parts) < 3:
            return "Usage: /rename-symbol <file> <old_name> <new_name>"

        import os

        path, old_name, new_name = parts[0], parts[1], parts[2]
        if not os.path.isfile(path):
            return f"File not found: {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        propagator = RenamePropagator()
        refs = propagator.find_references(source, old_name, file=path)
        if not refs:
            return f"No references to '{old_name}' found."
        updated = propagator.rename(source, old_name, new_name)
        return (
            f"Found {len(refs)} reference(s) to '{old_name}'.\n"
            f"Preview:\n{updated}"
        )

    # ------------------------------------------------------------------
    # /inline
    # ------------------------------------------------------------------

    async def inline_handler(args: str) -> str:
        from lidco.smart_refactor.inline_engine import InlineEngine

        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /inline <file> <var_name>"

        import os

        path, var_name = parts[0], parts[1]
        if not os.path.isfile(path):
            return f"File not found: {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()

        engine = InlineEngine()
        result = engine.inline_variable(source, var_name)
        if not result.success:
            return f"Inline failed: {result.error}"
        return engine.preview(result)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("detect-refactor", "Detect code smells and refactoring opportunities", detect_refactor_handler))
    registry.register(SlashCommand("extract", "Extract method from code", extract_handler))
    registry.register(SlashCommand("rename-symbol", "Rename symbol across file", rename_symbol_handler))
    registry.register(SlashCommand("inline", "Inline variable into usages", inline_handler))
