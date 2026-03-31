"""Q163 CLI commands: /ast, /repomap, /ast-lint."""
from __future__ import annotations

import json
import os

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q163 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /ast parse <file>
    # ------------------------------------------------------------------

    async def ast_handler(args: str) -> str:
        from lidco.ast.treesitter_parser import TreeSitterParser
        from lidco.ast.universal_extractor import UniversalExtractor

        if "parser" not in _state:
            _state["parser"] = TreeSitterParser()
        if "extractor" not in _state:
            _state["extractor"] = UniversalExtractor(_state["parser"])  # type: ignore[arg-type]

        parser: TreeSitterParser = _state["parser"]  # type: ignore[assignment]
        extractor: UniversalExtractor = _state["extractor"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "parse":
            if not rest:
                return "Usage: /ast parse <file>"
            file_path = rest
            lang = parser.detect_language(file_path)
            if lang is None:
                return f"Cannot detect language for: {file_path}"
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    source = fh.read()
            except Exception as exc:
                return f"Cannot read file: {exc}"
            result = parser.parse(source, lang)
            symbols = extractor.extract(source, lang)
            lines = [
                f"File: {file_path}",
                f"Language: {result.language}",
                f"Tree-sitter: {'yes' if result.tree_available else 'no (regex fallback)'}",
                f"Nodes: {result.node_count}",
                f"Errors: {len(result.errors)}",
                f"Symbols: {len(symbols)}",
            ]
            if result.errors:
                lines.append("Parse errors:")
                for e in result.errors[:10]:
                    lines.append(f"  - {e}")
            if symbols:
                lines.append("Symbols:")
                for s in symbols[:20]:
                    lines.append(f"  {s.kind}: {s.name} (L{s.line})")
            return "\n".join(lines)

        return (
            "Usage: /ast <subcommand>\n"
            "  parse <file>  — parse file and show AST info"
        )

    # ------------------------------------------------------------------
    # /repomap [--full] [path]
    # ------------------------------------------------------------------

    async def repomap_handler(args: str) -> str:
        from lidco.ast.treesitter_parser import TreeSitterParser
        from lidco.ast.universal_extractor import UniversalExtractor
        from lidco.ast.repo_map import MultiLanguageRepoMap

        if "parser" not in _state:
            _state["parser"] = TreeSitterParser()
        if "extractor" not in _state:
            _state["extractor"] = UniversalExtractor(_state["parser"])  # type: ignore[arg-type]

        parser: TreeSitterParser = _state["parser"]  # type: ignore[assignment]
        extractor: UniversalExtractor = _state["extractor"]  # type: ignore[assignment]

        parts = args.strip().split()
        full = "--full" in parts
        parts = [p for p in parts if p != "--full"]
        root = parts[0] if parts else os.getcwd()

        max_files = 500 if full else 50
        rmap = MultiLanguageRepoMap(extractor, max_files=max_files)
        entries = rmap.build(root)
        if not entries:
            return f"No supported source files found in: {root}"
        text = rmap.format_map(entries)
        total_symbols = sum(len(e.symbols) for e in entries)
        header = (
            f"Repo map: {len(entries)} files, {total_symbols} symbols"
            f" ({'full' if full else 'summary'})\n\n"
        )
        return header + text

    # ------------------------------------------------------------------
    # /ast-lint <file>
    # ------------------------------------------------------------------

    async def ast_lint_handler(args: str) -> str:
        from lidco.ast.treesitter_parser import TreeSitterParser
        from lidco.ast.ast_linter import ASTLinter

        if "parser" not in _state:
            _state["parser"] = TreeSitterParser()

        parser: TreeSitterParser = _state["parser"]  # type: ignore[assignment]
        linter = ASTLinter(parser)

        file_path = args.strip()
        if not file_path:
            return "Usage: /ast-lint <file>"

        result = linter.lint_file(file_path)
        lines = [
            f"File: {result.file_path}",
            f"Language: {result.language}",
            f"Valid: {'yes' if result.valid else 'NO'}",
        ]
        if result.errors:
            lines.append(f"Errors ({len(result.errors)}):")
            for e in result.errors[:20]:
                lines.append(f"  - {e}")
            suggestions = linter.auto_fix_suggestions(result)
            if suggestions:
                lines.append("Suggestions:")
                for s in suggestions:
                    lines.append(f"  - {s}")
        if result.warnings:
            lines.append(f"Warnings ({len(result.warnings)}):")
            for w in result.warnings[:10]:
                lines.append(f"  - {w}")
        return "\n".join(lines)

    registry.register(SlashCommand("ast", "Parse file and show AST info", ast_handler))
    registry.register(SlashCommand("repomap", "Generate multi-language repo map", repomap_handler))
    registry.register(SlashCommand("ast-lint", "Lint file using AST analysis", ast_lint_handler))
