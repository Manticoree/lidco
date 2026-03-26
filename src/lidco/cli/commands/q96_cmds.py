"""
Q96 CLI commands — /http, /sql, /profile, /undo

Registered via register_q96_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q96_commands(registry) -> None:
    """Register Q96 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /http — Make HTTP requests
    # ------------------------------------------------------------------
    async def http_handler(args: str) -> str:
        """
        Usage: /http <METHOD> <url> [--header K=V ...] [--json '{...}'] [--form K=V ...] [--bearer TOKEN] [--timeout N]
        """
        from lidco.tools.http_tool import HttpTool
        import json as _json

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /http <METHOD> <url> [options]\n"
                "Methods: GET POST PUT DELETE PATCH\n"
                "Options:\n"
                "  --header K=V       add request header\n"
                "  --json '{...}'     JSON request body\n"
                "  --form K=V         form field\n"
                "  --bearer TOKEN     Authorization: Bearer\n"
                "  --timeout N        timeout in seconds (default 30)\n"
                "Example: /http GET https://httpbin.org/get --header Accept=application/json"
            )

        method = parts[0].upper()
        if len(parts) < 2:
            return "Error: URL required after method."
        url = parts[1]

        headers: dict[str, str] = {}
        form_data: dict[str, str] = {}
        json_data = None
        bearer: str | None = None
        timeout = 30.0
        i = 2
        while i < len(parts):
            tok = parts[i]
            if tok == "--header" and i + 1 < len(parts):
                i += 1
                k, _, v = parts[i].partition("=")
                headers[k.strip()] = v.strip()
            elif tok == "--json" and i + 1 < len(parts):
                i += 1
                try:
                    json_data = _json.loads(parts[i])
                except _json.JSONDecodeError as exc:
                    return f"Error parsing --json: {exc}"
            elif tok == "--form" and i + 1 < len(parts):
                i += 1
                k, _, v = parts[i].partition("=")
                form_data[k.strip()] = v.strip()
            elif tok == "--bearer" and i + 1 < len(parts):
                i += 1
                bearer = parts[i]
            elif tok == "--timeout" and i + 1 < len(parts):
                i += 1
                try:
                    timeout = float(parts[i])
                except ValueError:
                    return f"Error: --timeout must be a number, got '{parts[i]}'"
            i += 1

        try:
            tool = HttpTool(default_timeout=timeout)
            resp = tool.request(
                method, url,
                headers=headers or None,
                json_data=json_data,
                form_data=form_data or None,
                bearer=bearer,
                timeout=timeout,
            )
            return resp.format_summary()
        except Exception as exc:
            return f"Error: {exc}"

    registry.register_async("http", "Make HTTP requests (GET/POST/PUT/DELETE/PATCH)", http_handler)

    # ------------------------------------------------------------------
    # /sql — Execute SQL against a SQLite database
    # ------------------------------------------------------------------
    async def sql_handler(args: str) -> str:
        """
        Usage: /sql [--db <path>] <SQL query>
               /sql [--db <path>] tables
               /sql [--db <path>] schema <tablename>
        """
        from lidco.tools.sql_tool import SqlTool

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /sql [--db <path>] <SQL query>\n"
                "       /sql [--db <path>] tables\n"
                "       /sql [--db <path>] schema <tablename>\n"
                "Default db: :memory:\n"
                "Example: /sql --db myapp.db SELECT * FROM users LIMIT 10"
            )

        db_path = ":memory:"
        i = 0
        if parts[0] == "--db" and len(parts) > 1:
            db_path = parts[1]
            i = 2

        remaining = parts[i:]
        if not remaining:
            return "Error: SQL query or subcommand required."

        try:
            tool = SqlTool(db_path=db_path)
            tool.connect()

            if remaining[0].lower() == "tables":
                tables = tool.list_tables()
                if not tables:
                    return "No tables found in database."
                return "Tables:\n" + "\n".join(f"  {t}" for t in tables)

            if remaining[0].lower() == "schema" and len(remaining) >= 2:
                info = tool.table_info(remaining[1])
                lines = [f"Table: {info.name} ({info.row_count} rows)"]
                for col in info.columns:
                    pk = " PK" if col["pk"] else ""
                    nn = " NOT NULL" if col["notnull"] else ""
                    df = f" DEFAULT {col['default']}" if col["default"] is not None else ""
                    lines.append(f"  {col['name']} {col['type']}{pk}{nn}{df}")
                return "\n".join(lines)

            query = " ".join(remaining)
            result = tool.execute(query)
            tool.close()
            return result.format_table()
        except Exception as exc:
            return f"Error: {exc}"

    registry.register_async("sql", "Execute SQL queries against SQLite databases", sql_handler)

    # ------------------------------------------------------------------
    # /profile — Profile Python code performance
    # ------------------------------------------------------------------
    async def profile_handler(args: str) -> str:
        """
        Usage: /profile file <path> [--top N]
               /profile code <python snippet>
        """
        from lidco.profiling.profiler import CodeProfiler

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /profile file <path.py> [--top N]\n"
                "       /profile code <python code>\n"
                "Example: /profile file src/mymodule.py --top 10"
            )

        top = 10
        # parse --top
        filtered = []
        i = 0
        while i < len(parts):
            if parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                filtered.append(parts[i])
                i += 1
        parts = filtered

        if not parts:
            return "Error: subcommand required (file or code)."

        subcmd = parts[0].lower()
        profiler = CodeProfiler()

        try:
            if subcmd == "file":
                if len(parts) < 2:
                    return "Error: file path required."
                report = profiler.profile_file(parts[1])
            elif subcmd == "code":
                if len(parts) < 2:
                    return "Error: code snippet required."
                code_snippet = " ".join(parts[1:])
                report = profiler.profile_code(code_snippet)
            else:
                return f"Unknown subcommand '{subcmd}'. Use 'file' or 'code'."

            if not report.ok:
                return f"Profile error: {report.error}"
            return report.format_table(n=top)
        except Exception as exc:
            return f"Error: {exc}"

    registry.register_async("profile", "Profile Python code performance with cProfile", profile_handler)

    # ------------------------------------------------------------------
    # /undo — Undo/redo file changes
    # ------------------------------------------------------------------

    # Module-level UndoManager shared across handler calls in the same session
    _undo_manager: dict[str, object] = {}

    async def undo_handler(args: str) -> str:
        """
        Usage: /undo checkpoint [<label>] [<file1> ...]
               /undo undo
               /undo redo
               /undo history
               /undo watch <file1> [file2 ...]
        """
        from lidco.editing.undo_manager import UndoManager

        if "manager" not in _undo_manager:
            _undo_manager["manager"] = UndoManager()
        mgr: UndoManager = _undo_manager["manager"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "history"

        if subcmd == "checkpoint":
            label = parts[1] if len(parts) > 1 else "manual"
            extra = parts[2:] if len(parts) > 2 else []
            cp = mgr.checkpoint(label=label, extra_files=extra or None)
            return f"Checkpoint saved: {cp.summary()}"

        if subcmd == "undo":
            result = mgr.undo()
            if result.success:
                files_str = ", ".join(result.restored_files) or "none"
                assert result.checkpoint is not None
                return f"Undone to: {result.checkpoint.summary()}\nRestored: {files_str}"
            return f"Cannot undo: {result.error}"

        if subcmd == "redo":
            result = mgr.redo()
            if result.success:
                files_str = ", ".join(result.restored_files) or "none"
                assert result.checkpoint is not None
                return f"Redone to: {result.checkpoint.summary()}\nRestored: {files_str}"
            return f"Cannot redo: {result.error}"

        if subcmd == "watch":
            if len(parts) < 2:
                return "Error: specify files to watch."
            mgr.watch(*parts[1:])
            return f"Now watching: {', '.join(mgr.watched_files)}"

        if subcmd == "history":
            history = mgr.list_history()
            redo = mgr.list_redo()
            lines = []
            if history:
                lines.append("Undo history (oldest → newest):")
                for h in history:
                    lines.append(f"  {h}")
            else:
                lines.append("No undo history.")
            if redo:
                lines.append("Redo stack:")
                for r in redo:
                    lines.append(f"  {r}")
            lines.append(f"Can undo: {mgr.can_undo}  Can redo: {mgr.can_redo}")
            return "\n".join(lines)

        return (
            "Usage: /undo <subcommand>\n"
            "Subcommands:\n"
            "  checkpoint [label] [files...]  save current file state\n"
            "  undo                           restore previous checkpoint\n"
            "  redo                           re-apply undone checkpoint\n"
            "  watch <files...>               add files to watch list\n"
            "  history                        show undo/redo history"
        )

    registry.register_async("undo", "Undo/redo file changes via checkpoints", undo_handler)
