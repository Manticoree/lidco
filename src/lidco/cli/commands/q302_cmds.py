"""
Q302 CLI commands — /git-analyze, /smart-blame, /auto-bisect, /git-search

Registered via register_q302_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q302_commands(registry) -> None:
    """Register Q302 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /git-analyze — commit analytics and hotspots
    # ------------------------------------------------------------------
    async def git_analyze_handler(args: str) -> str:
        """
        Usage: /git-analyze summary
               /git-analyze contributors
               /git-analyze hotspots [N]
               /git-analyze churn
               /git-analyze cadence
        """
        from datetime import datetime

        from lidco.githistory.analyzer import HistoryAnalyzer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /git-analyze <subcommand>\n"
                "  summary        high-level repo summary\n"
                "  contributors   per-author stats\n"
                "  hotspots [N]   top-N most changed files\n"
                "  churn          all files sorted by change count\n"
                "  cadence        commit frequency stats"
            )

        analyzer = HistoryAnalyzer()
        # In a real integration we'd parse git log; here we return the empty analyzer info.
        subcmd = parts[0].lower()

        if subcmd == "summary":
            return str(analyzer.summary())
        if subcmd == "contributors":
            stats = analyzer.contributor_stats()
            if not stats:
                return "No commits loaded. Feed data via the API or integrate with git log."
            lines = []
            for author, info in stats.items():
                lines.append(f"  {author}: {info['commit_count']} commits, {len(info['files_touched'])} files")
            return "Contributors:\n" + "\n".join(lines)
        if subcmd == "hotspots":
            top_n = 10
            if len(parts) > 1:
                try:
                    top_n = int(parts[1])
                except ValueError:
                    return f"Error: N must be an integer, got {parts[1]!r}"
            spots = analyzer.hotspots(top_n)
            if not spots:
                return "No hotspot data. Load commits first."
            lines = [f"  {f}: {n} changes" for f, n in spots]
            return "Hotspots:\n" + "\n".join(lines)
        if subcmd == "churn":
            churn = analyzer.file_churn()
            if not churn:
                return "No churn data."
            lines = [f"  {f}: {n}" for f, n in churn]
            return "File churn:\n" + "\n".join(lines)
        if subcmd == "cadence":
            return str(analyzer.release_cadence())

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("git-analyze", "Commit analytics and hotspot detection", git_analyze_handler)

    # ------------------------------------------------------------------
    # /smart-blame — blame with skip-formatting
    # ------------------------------------------------------------------
    async def smart_blame_handler(args: str) -> str:
        """
        Usage: /smart-blame <file> [start_line end_line]
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /smart-blame <file> [start_line end_line]\n"
                "  Shows blame for a file, skipping formatting-only commits."
            )

        from lidco.githistory.blame import BlameIntelligence

        bi = BlameIntelligence()
        file_path = parts[0]
        # Without real git integration, return a placeholder
        return f"BlameIntelligence ready for '{file_path}'. Integrate with git blame output for results."

    registry.register_async("smart-blame", "Smart blame skipping formatting commits", smart_blame_handler)

    # ------------------------------------------------------------------
    # /auto-bisect — guided binary-search bisect
    # ------------------------------------------------------------------
    _bisect_state: dict[str, object] = {}

    async def auto_bisect_handler(args: str) -> str:
        """
        Usage: /auto-bisect start <good> <bad> <commit1,commit2,...>
               /auto-bisect test pass|fail
               /auto-bisect status
               /auto-bisect reset
        """
        from lidco.githistory.bisect import BisectAssistant

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /auto-bisect <subcommand>\n"
                "  start <good> <bad> <c1,c2,...>  begin bisect\n"
                "  test pass|fail                   record test result\n"
                "  status                           show current state\n"
                "  reset                            clear bisect session"
            )

        subcmd = parts[0].lower()

        if subcmd == "start":
            if len(parts) < 4:
                return "Error: Usage: /auto-bisect start <good> <bad> <c1,c2,...>"
            good, bad = parts[1], parts[2]
            commits = parts[3].split(",")
            ba = BisectAssistant()
            try:
                ba.start(good, bad, commits)
            except ValueError as exc:
                return f"Error: {exc}"
            _bisect_state["assistant"] = ba
            return f"Bisect started. Test commit: {ba.current()} ({ba.steps_remaining()} steps est.)"

        if subcmd == "test":
            if "assistant" not in _bisect_state:
                return "Error: no bisect session. Use /auto-bisect start first."
            if len(parts) < 2:
                return "Error: specify pass or fail"
            ba: BisectAssistant = _bisect_state["assistant"]  # type: ignore[assignment]
            passed = parts[1].lower() in ("pass", "true", "yes", "1")
            result = ba.test_commit(ba.current(), passed)
            if result == "found":
                return f"Found bad commit: {ba.found()}"
            return f"Next commit to test: {result} ({ba.steps_remaining()} steps est.)"

        if subcmd == "status":
            if "assistant" not in _bisect_state:
                return "No active bisect session."
            ba = _bisect_state["assistant"]  # type: ignore[assignment]
            found = ba.found()
            if found:
                return f"Bisect complete. Bad commit: {found}"
            return f"Current: {ba.current()}, steps remaining: ~{ba.steps_remaining()}, history: {len(ba.history())} tests"

        if subcmd == "reset":
            _bisect_state.clear()
            return "Bisect session cleared."

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("auto-bisect", "Guided binary-search git bisect", auto_bisect_handler)

    # ------------------------------------------------------------------
    # /git-search — search commit messages and diffs
    # ------------------------------------------------------------------
    async def git_search_handler(args: str) -> str:
        """
        Usage: /git-search messages <query>
               /git-search diffs <pattern>
               /git-search author <name>
        """
        from lidco.githistory.search import HistorySearch

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /git-search <subcommand>\n"
                "  messages <query>    search commit messages\n"
                "  diffs <pattern>     search diffs with regex\n"
                "  author <name>       filter by author"
            )

        hs = HistorySearch()
        subcmd = parts[0].lower()

        if subcmd == "messages":
            if len(parts) < 2:
                return "Error: query required."
            results = hs.search_messages(parts[1])
            if not results:
                return "No matching commits. Load history via the API first."
            lines = [f"  {r.hash[:8]} {r.message}" for r in results]
            return "Matches:\n" + "\n".join(lines)

        if subcmd == "diffs":
            if len(parts) < 2:
                return "Error: pattern required."
            results = hs.search_diffs(parts[1])
            if not results:
                return "No matching diffs."
            lines = [f"  {r.hash[:8]} {r.match_context}" for r in results]
            return "Diff matches:\n" + "\n".join(lines)

        if subcmd == "author":
            if len(parts) < 2:
                return "Error: author name required."
            results = hs.by_author(parts[1])
            if not results:
                return "No commits by that author."
            lines = [f"  {r.hash[:8]} {r.message}" for r in results]
            return "By author:\n" + "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("git-search", "Search commit messages and diffs", git_search_handler)
