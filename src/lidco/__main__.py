"""LIDCO - LLM-Integrated Development COmpanion."""

import asyncio
import sys

# Force UTF-8 I/O on Windows (prevents charmap UnicodeDecodeError with non-ASCII content).
# Must happen before any other imports that touch stdin/stdout/stderr.
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    # Also wrap stdin to avoid charmap errors when reading user input
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPL_HELP = """\
Usage: lidco [OPTIONS]
       lidco exec [OPTIONS] [TASK]
       lidco precommit [OPTIONS]
       lidco index [--incremental] [--codemap] [--dir <path>]
       lidco serve [--host <host>] [--port <port>]
       lidco mcp-server

REPL options:
  --agent <name>     Start with a specific agent (e.g. coder, reviewer, planner)
  --model <name>     Override the default LLM model for this session
  --no-review        Disable automatic post-response code review
  --no-plan          Disable automatic pre-task planning
  --no-streaming     Disable token streaming (show response all at once)
  --timeout <secs>   Agent timeout in seconds (default: 600, 0 = no timeout)
  --help, -h         Show this help message and exit

exec options (headless CI/CD mode):
  --json             Output structured JSON instead of plain text
  --quiet            Suppress all stderr output
  --agent <name>     Use a specific agent
  --model <name>     Override LLM model
  --permission-mode  bypass|plan|default (default: from config)
  --no-plan          Skip pre-task planning
  --no-review        Skip post-task review
  --max-turns <n>    Cap agent iterations
  --project-dir <p>  Project root (default: cwd)

precommit options (pre-commit hook):
  --json             Output structured JSON
  --quiet            Suppress status output
  --agent <name>     Agent to use (default: security)
  --max-turns <n>    Cap iterations (default: 10)

Examples:
  lidco exec "fix all failing tests"
  lidco exec --json "add docstrings to src/api/"
  lidco exec --permission-mode bypass --max-turns 20 "refactor utils.py"
  echo "task" | lidco exec
  lidco precommit
  lidco --agent reviewer --no-plan
  lidco --model ollama/llama3.1 --no-streaming
  lidco --timeout 0
"""


@dataclass
class CLIFlags:
    """Flags parsed from the command line for the REPL."""

    agent: str | None = None
    model: str | None = None
    no_review: bool = False
    no_plan: bool = False
    no_streaming: bool = False
    timeout: int | None = None  # None = use config value; 0 = no timeout
    from_pr: int | None = None  # Task 380: --from-pr <number>
    session_name: str | None = None  # Task 383: --session <name>
    profile_name: str | None = None  # Task 385: --profile <name>


def main() -> None:
    """Entry point for the lidco CLI."""
    args = sys.argv[1:]

    if args and args[0] == "serve":
        _run_serve(args[1:])
    elif args and args[0] == "index":
        _run_index(args[1:])
    elif args and args[0] == "exec":
        _run_exec(args[1:])
    elif args and args[0] == "precommit":
        _run_precommit(args[1:])
    elif args and args[0] == "mcp-server":
        _run_mcp_server(args[1:])
    else:
        if "--help" in args or "-h" in args:
            print(_REPL_HELP)
            sys.exit(0)
        flags = _parse_repl_flags(args)
        from lidco.cli.app import run_cli
        run_cli(flags=flags)


def _parse_repl_flags(args: list[str]) -> CLIFlags:
    """Parse REPL-mode flags from argv."""
    flags = CLIFlags()
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--no-review":
            flags.no_review = True
            i += 1
        elif arg == "--no-plan":
            flags.no_plan = True
            i += 1
        elif arg == "--no-streaming":
            flags.no_streaming = True
            i += 1
        elif arg == "--agent" and i + 1 < len(args):
            flags.agent = args[i + 1]
            i += 2
        elif arg == "--model" and i + 1 < len(args):
            flags.model = args[i + 1]
            i += 2
        elif arg == "--timeout" and i + 1 < len(args):
            try:
                flags.timeout = int(args[i + 1])
            except ValueError:
                print(f"--timeout requires an integer (seconds), got: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg == "--from-pr" and i + 1 < len(args):
            try:
                flags.from_pr = int(args[i + 1])
            except ValueError:
                print(f"--from-pr requires a PR number (integer), got: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg == "--session" and i + 1 < len(args):
            flags.session_name = args[i + 1]
            i += 2
        elif arg == "--profile" and i + 1 < len(args):
            flags.profile_name = args[i + 1]
            i += 2
        else:
            print(f"Unknown argument: {arg}")
            print("Run 'lidco --help' for usage.")
            sys.exit(1)
    return flags


def _run_serve(args: list[str]) -> None:
    """Parse serve sub-command flags and start the HTTP server."""
    host = "127.0.0.1"
    port = 8321
    project_dir: Path | None = None

    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--project-dir" and i + 1 < len(args):
            project_dir = Path(args[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {args[i]}")
            sys.exit(1)

    from lidco.server.app import run_server

    run_server(host=host, port=port, project_dir=project_dir)


def _run_index(args: list[str]) -> None:
    """Parse index sub-command flags and run the structural indexer."""
    incremental = False
    write_codemap = False
    project_dir = Path.cwd()

    i = 0
    while i < len(args):
        if args[i] == "--incremental":
            incremental = True
            i += 1
        elif args[i] == "--codemap":
            write_codemap = True
            i += 1
        elif args[i] == "--dir" and i + 1 < len(args):
            project_dir = Path(args[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {args[i]}")
            print("Usage: lidco index [--incremental] [--codemap] [--dir <path>]")
            sys.exit(1)

    from lidco.index.codemap_generator import CodemapGenerator
    from lidco.index.db import IndexDatabase
    from lidco.index.project_indexer import ProjectIndexer

    db_path = project_dir / ".lidco" / "project_index.db"
    db = IndexDatabase(db_path)

    try:
        indexer = ProjectIndexer(project_dir=project_dir, db=db)

        # Use incremental only if explicitly requested AND index already has data
        use_incremental = incremental and db.get_stats().total_files > 0

        total_files: list[int] = [0]

        def _progress(i: int, n: int, name: str) -> None:
            total_files[0] = n
            print(f"\r  [{i}/{n}] {name:<50}", end="", flush=True)

        print(f"Indexing {project_dir} ({'incremental' if use_incremental else 'full'})...")

        if use_incremental:
            result = indexer.run_incremental_index(progress_callback=_progress)
        else:
            result = indexer.run_full_index(progress_callback=_progress)

        if total_files[0]:
            print()  # newline after progress

        s = result.stats
        print(
            f"\nDone: +{result.added} added, {result.updated} updated, "
            f"{result.deleted} deleted, {result.skipped} skipped"
        )
        print(f"Total: {s.total_files} files · {s.total_symbols} symbols · {s.total_imports} imports")

        if s.files_by_language:
            lang_str = ", ".join(
                f"{cnt} {lang}"
                for lang, cnt in sorted(s.files_by_language.items(), key=lambda x: -x[1])
            )
            print(f"Languages: {lang_str}")

        if write_codemap:
            codemap_path = project_dir / "CODEMAPS.md"
            gen = CodemapGenerator(db)
            gen.write(codemap_path)
            print(f"Codemap written to {codemap_path}")

    finally:
        db.close()


def _run_exec(args: list[str]) -> None:
    """Parse exec sub-command flags and run headless mode."""
    from lidco.cli.exec_mode import ExecFlags, run_exec
    from lidco.cli.exit_codes import CONFIG_ERROR

    flags = ExecFlags()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            flags.json = True
            i += 1
        elif a == "--quiet" or a == "-q":
            flags.quiet = True
            i += 1
        elif a == "--no-plan":
            flags.no_plan = True
            i += 1
        elif a == "--no-review":
            flags.no_review = True
            i += 1
        elif a in ("--agent", "--model", "--permission-mode", "--max-turns", "--project-dir") and i + 1 < len(args):
            val = args[i + 1]
            if a == "--agent":
                flags.agent = val
            elif a == "--model":
                flags.model = val
            elif a == "--permission-mode":
                flags.permission_mode = val
            elif a == "--max-turns":
                try:
                    flags.max_turns = int(val)
                except ValueError:
                    sys.stderr.write(f"--max-turns requires an integer, got: {val}\n")
                    sys.exit(CONFIG_ERROR)
            elif a == "--project-dir":
                flags.project_dir = val
            i += 2
        elif not a.startswith("-"):
            # Remaining positional args form the task
            flags.task = " ".join(args[i:])
            break
        else:
            sys.stderr.write(f"Unknown argument: {a}\n")
            sys.stderr.write("Run 'lidco exec --help' for usage.\n")
            sys.exit(CONFIG_ERROR)

    exit_code = asyncio.run(run_exec(flags))
    sys.exit(exit_code)


def _run_precommit(args: list[str]) -> None:
    """Parse precommit sub-command flags and run pre-commit check."""
    from lidco.cli.exec_mode import PrecommitFlags, run_precommit
    from lidco.cli.exit_codes import CONFIG_ERROR

    flags = PrecommitFlags()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            flags.json = True
            i += 1
        elif a == "--quiet" or a == "-q":
            flags.quiet = True
            i += 1
        elif a in ("--agent", "--model", "--max-turns", "--project-dir") and i + 1 < len(args):
            val = args[i + 1]
            if a == "--agent":
                flags.agent = val
            elif a == "--model":
                flags.model = val
            elif a == "--max-turns":
                try:
                    flags.max_turns = int(val)
                except ValueError:
                    sys.stderr.write(f"--max-turns requires an integer, got: {val}\n")
                    sys.exit(CONFIG_ERROR)
            elif a == "--project-dir":
                flags.project_dir = val
            i += 2
        else:
            sys.stderr.write(f"Unknown argument: {a}\n")
            sys.exit(CONFIG_ERROR)

    exit_code = asyncio.run(run_precommit(flags))
    sys.exit(exit_code)


def _run_mcp_server(args: list[str]) -> None:
    """Start LIDCO as an MCP server over stdio (Task 259)."""
    from lidco.core.session import Session
    from lidco.mcp.server import MCPServer

    session = Session()

    async def _serve() -> None:
        server = MCPServer(session.tool_registry)
        await server.serve_stdio()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
