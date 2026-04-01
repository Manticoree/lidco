"""
Q190 CLI commands — /lsp-start, /goto-def, /find-refs, /diagnostics

Registered via register_q190_commands(registry).
"""
from __future__ import annotations

import shlex


# Module-level shared state for the LSP client instance
_lsp_state: dict[str, object] = {}


def register_q190_commands(registry) -> None:
    """Register Q190 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /lsp-start — Start an LSP server
    # ------------------------------------------------------------------
    async def lsp_start_handler(args: str) -> str:
        """
        Usage: /lsp-start <command> [args...]
               /lsp-start stop
               /lsp-start status
        """
        from lidco.lsp.client import LSPClient

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /lsp-start <subcommand>\n"
                "  <command> [args...]  start an LSP server\n"
                "  stop                 stop the running server\n"
                "  status               show server status and capabilities"
            )

        subcmd = parts[0].lower()

        if subcmd == "stop":
            client = _lsp_state.get("client")
            if client is None:
                return "No LSP server is running."
            client.stop()  # type: ignore[union-attr]
            _lsp_state.pop("client", None)
            return "LSP server stopped."

        if subcmd == "status":
            client = _lsp_state.get("client")
            if client is None or not client.is_running:  # type: ignore[union-attr]
                return "LSP server is not running."
            caps = client.capabilities  # type: ignore[union-attr]
            if caps:
                cap_list = "\n".join(f"  {c}" for c in sorted(caps))
                return f"LSP server is running.\nCapabilities:\n{cap_list}"
            return "LSP server is running (no capabilities reported)."

        # Start a new server
        command = parts[0]
        server_args = tuple(parts[1:])
        client = LSPClient(command, server_args)
        ok = client.start()
        if not ok:
            return f"Failed to start LSP server: {command}"
        _lsp_state["client"] = client
        caps = client.capabilities
        cap_note = f" Capabilities: {', '.join(sorted(caps))}" if caps else ""
        return f"LSP server started: {command}{cap_note}"

    registry.register_async("lsp-start", "Start/stop/status of LSP server", lsp_start_handler)

    # ------------------------------------------------------------------
    # /goto-def — Go to definition
    # ------------------------------------------------------------------
    async def goto_def_handler(args: str) -> str:
        """
        Usage: /goto-def <file> <line> <col>
               /goto-def --type <file> <line> <col>
               /goto-def --impl <file> <line> <col>
        """
        from lidco.lsp.definitions import DefinitionResolver

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 3:
            return (
                "Usage: /goto-def <file> <line> <col>\n"
                "  --type  go to type definition\n"
                "  --impl  go to implementation(s)"
            )

        client = _lsp_state.get("client")
        if client is None:
            return "Error: No LSP server running. Use /lsp-start first."

        resolver = DefinitionResolver(client)  # type: ignore[arg-type]

        mode = "def"
        if parts[0] == "--type":
            mode = "type"
            parts = parts[1:]
        elif parts[0] == "--impl":
            mode = "impl"
            parts = parts[1:]

        if len(parts) < 3:
            return "Error: file, line, and col are required."

        file_path = parts[0]
        try:
            line = int(parts[1])
            col = int(parts[2])
        except ValueError:
            return "Error: line and col must be integers."

        if mode == "type":
            loc = resolver.goto_type_definition(file_path, line, col)
            if loc is None:
                return "No type definition found."
            return f"Type definition: {loc.file}:{loc.line}:{loc.column}"

        if mode == "impl":
            locs = resolver.goto_implementation(file_path, line, col)
            if not locs:
                return "No implementations found."
            lines = [f"  {loc.file}:{loc.line}:{loc.column}" for loc in locs]
            return f"Implementations ({len(locs)}):\n" + "\n".join(lines)

        loc = resolver.goto_definition(file_path, line, col)
        if loc is None:
            return "No definition found."
        return f"Definition: {loc.file}:{loc.line}:{loc.column}"

    registry.register_async("goto-def", "Go to definition/type/implementation via LSP", goto_def_handler)

    # ------------------------------------------------------------------
    # /find-refs — Find references
    # ------------------------------------------------------------------
    async def find_refs_handler(args: str) -> str:
        """
        Usage: /find-refs <file> <line> <col> [--decl]
               /find-refs --symbols <query>
               /find-refs --calls <file> <line> <col>
        """
        from lidco.lsp.references import ReferenceFinder

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /find-refs <file> <line> <col> [--decl]\n"
                "  --symbols <query>        search workspace symbols\n"
                "  --calls <file> <line> <col>  show call hierarchy"
            )

        client = _lsp_state.get("client")
        if client is None:
            return "Error: No LSP server running. Use /lsp-start first."

        finder = ReferenceFinder(client)  # type: ignore[arg-type]

        if parts[0] == "--symbols":
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            symbols = finder.find_workspace_symbols(query)
            if not symbols:
                return "No symbols found."
            lines = [f"  {s.name} ({s.container_name or 'global'}) — {s.file}:{s.line}" for s in symbols[:20]]
            return f"Workspace symbols ({len(symbols)}):\n" + "\n".join(lines)

        if parts[0] == "--calls":
            if len(parts) < 4:
                return "Error: file, line, and col are required for --calls."
            try:
                line = int(parts[2])
                col = int(parts[3])
            except ValueError:
                return "Error: line and col must be integers."
            node = finder.call_hierarchy(parts[1], line, col)
            if node is None:
                return "No call hierarchy found."
            lines = [f"  {node.name} — {node.file}:{node.line}"]
            for child in node.children:
                lines.append(f"    <- {child.name} — {child.file}:{child.line}")
            return "Call hierarchy:\n" + "\n".join(lines)

        if len(parts) < 3:
            return "Error: file, line, and col are required."

        file_path = parts[0]
        try:
            line = int(parts[1])
            col = int(parts[2])
        except ValueError:
            return "Error: line and col must be integers."

        include_decl = "--decl" in parts[3:]
        refs = finder.find_references(file_path, line, col, include_declaration=include_decl)
        if not refs:
            return "No references found."
        lines = [f"  {r.file}:{r.line}:{r.column}" for r in refs[:30]]
        more = f"\n  ... and {len(refs) - 30} more" if len(refs) > 30 else ""
        return f"References ({len(refs)}):\n" + "\n".join(lines) + more

    registry.register_async("find-refs", "Find references, symbols, and call hierarchy via LSP", find_refs_handler)

    # ------------------------------------------------------------------
    # /diagnostics — Collect diagnostics
    # ------------------------------------------------------------------
    async def diagnostics_handler(args: str) -> str:
        """
        Usage: /diagnostics <file>
               /diagnostics --all
               /diagnostics --summary
        """
        from lidco.lsp.diagnostics import DiagnosticsCollector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /diagnostics <file>\n"
                "  --all      collect diagnostics for all open files\n"
                "  --summary  show severity counts from cache"
            )

        client = _lsp_state.get("client")
        if client is None:
            return "Error: No LSP server running. Use /lsp-start first."

        collector = DiagnosticsCollector(client)  # type: ignore[arg-type]

        if parts[0] == "--summary":
            counts = collector.severity_counts()
            if not counts:
                return "No diagnostics cached. Run /diagnostics <file> or /diagnostics --all first."
            lines = [f"  {k}: {v}" for k, v in sorted(counts.items())]
            return "Diagnostic severity counts:\n" + "\n".join(lines)

        if parts[0] == "--all":
            all_diags = collector.collect_all()
            if not all_diags:
                return "No diagnostics found."
            lines = []
            for file_path, diags in sorted(all_diags.items()):
                lines.append(f"  {file_path}: {len(diags)} diagnostic(s)")
                for d in diags[:5]:
                    lines.append(f"    [{d.severity.name}] L{d.line}:{d.column} {d.message}")
                if len(diags) > 5:
                    lines.append(f"    ... and {len(diags) - 5} more")
            return "Diagnostics:\n" + "\n".join(lines)

        file_path = parts[0]
        diags = collector.collect(file_path)
        if not diags:
            return f"No diagnostics for {file_path}."
        lines = [f"Diagnostics for {file_path} ({len(diags)}):"]
        for d in diags:
            lines.append(f"  [{d.severity.name}] L{d.line}:{d.column} {d.message}" +
                         (f" ({d.source})" if d.source else ""))
        return "\n".join(lines)

    registry.register_async("diagnostics", "Collect LSP diagnostics for files", diagnostics_handler)
