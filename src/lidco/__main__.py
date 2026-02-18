"""LIDCO - LLM-Integrated Development COmpanion."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPL_HELP = """\
Usage: lidco [OPTIONS]
       lidco index [--incremental] [--codemap] [--dir <path>]
       lidco serve [--host <host>] [--port <port>]

REPL options:
  --agent <name>     Start with a specific agent (e.g. coder, reviewer, planner)
  --model <name>     Override the default LLM model for this session
  --no-review        Disable automatic post-response code review
  --no-plan          Disable automatic pre-task planning
  --no-streaming     Disable token streaming (show response all at once)
  --help, -h         Show this help message and exit

Examples:
  lidco --agent reviewer --no-plan
  lidco --model ollama/llama3.1 --no-streaming
  lidco --no-review --no-plan
"""


@dataclass
class CLIFlags:
    """Flags parsed from the command line for the REPL."""

    agent: str | None = None
    model: str | None = None
    no_review: bool = False
    no_plan: bool = False
    no_streaming: bool = False


def main() -> None:
    """Entry point for the lidco CLI."""
    args = sys.argv[1:]

    if args and args[0] == "serve":
        _run_serve(args[1:])
    elif args and args[0] == "index":
        _run_index(args[1:])
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


if __name__ == "__main__":
    main()
