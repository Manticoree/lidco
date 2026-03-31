"""Q125 CLI commands: /symbols."""
from __future__ import annotations

_state: dict = {}


def register(registry) -> None:
    """Register Q125 commands."""
    from lidco.cli.commands.registry import SlashCommand

    async def symbols_handler(args: str) -> str:
        from lidco.analysis.symbol_index2 import SymbolIndex, SymbolDef, SymbolRef
        from lidco.analysis.python_extractor import PythonExtractor
        from lidco.analysis.cross_reference import CrossReference

        if "index" not in _state:
            _state["index"] = SymbolIndex()

        index: SymbolIndex = _state["index"]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "extract":
            if not rest:
                return "Usage: /symbols extract <python_code>"
            extractor = PythonExtractor()
            result = extractor.extract(rest, module_name="<input>")
            if result.errors:
                return f"Extraction errors: {'; '.join(result.errors)}"
            for sym in result.definitions:
                index.add_definition(sym)
            return (
                f"Extracted {len(result.definitions)} definition(s), "
                f"{len(result.imports)} import(s)."
            )

        if sub == "find":
            if not rest:
                return "Usage: /symbols find <name>"
            sym = index.find_definition(rest.strip())
            if sym is None:
                return f"Symbol '{rest.strip()}' not found."
            return (
                f"{sym.name} [{sym.kind}] in {sym.module}:{sym.line}"
                + (f" — {sym.docstring[:80]}" if sym.docstring else "")
            )

        if sub == "list":
            kind = rest.strip() or None
            syms = index.list_symbols(kind=kind)
            if not syms:
                return "No symbols found." if kind is None else f"No symbols of kind '{kind}'."
            lines = [f"Symbols ({len(syms)}):"]
            for s in syms[:20]:
                lines.append(f"  {s.name} [{s.kind}] {s.module}:{s.line}")
            if len(syms) > 20:
                lines.append(f"  ... and {len(syms) - 20} more")
            return "\n".join(lines)

        if sub == "xref":
            if not rest:
                return "Usage: /symbols xref <name>"
            xref = CrossReference(index)
            refs = xref.find_usages(rest.strip())
            defn = xref.find_definition(rest.strip())
            lines = []
            if defn:
                lines.append(f"Defined: {defn.module}:{defn.line}")
            else:
                lines.append("Not defined in index.")
            if refs:
                lines.append(f"References ({len(refs)}):")
                for r in refs[:10]:
                    lines.append(f"  {r.module}:{r.line}")
            else:
                lines.append("No references found.")
            return "\n".join(lines)

        if sub == "unused":
            xref = CrossReference(index)
            unused = xref.unused_definitions()
            if not unused:
                return "No unused definitions."
            lines = [f"Unused ({len(unused)}):"]
            for s in unused[:20]:
                lines.append(f"  {s.name} [{s.kind}] {s.module}:{s.line}")
            return "\n".join(lines)

        if sub == "clear":
            index.clear()
            _state.pop("index", None)
            return "Symbol index cleared."

        return (
            "Usage: /symbols <sub>\n"
            "  extract <code>   -- extract symbols from Python code\n"
            "  find <name>      -- find definition\n"
            "  list [kind]      -- list all symbols (optionally filter by kind)\n"
            "  xref <name>      -- cross-reference: definition + usages\n"
            "  unused           -- show unused definitions\n"
            "  clear            -- reset index"
        )

    registry.register(SlashCommand("symbols", "Symbol index and cross-reference", symbols_handler))
