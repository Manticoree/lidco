"""Q120 CLI commands: /memory, /session, /transcript, /summary."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q120 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /memory consolidate                                                  #
    # ------------------------------------------------------------------ #

    async def memory_handler(args: str) -> str:
        from lidco.memory.consolidation_scheduler import AsyncConsolidationScheduler

        if "scheduler" not in _state:
            _state["scheduler"] = AsyncConsolidationScheduler(consolidator=None)

        sched: AsyncConsolidationScheduler = _state["scheduler"]  # type: ignore[assignment]

        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "consolidate":
            dry_run = "--dry-run" in args
            if dry_run:
                return "[dry-run] Memory consolidation would run here."
            job = sched.run_once()
            if job.status == "completed":
                return f"Consolidation complete. Run count: {job.run_count}"
            elif job.status == "failed":
                return f"Consolidation failed: {job.error or 'no consolidator'}"
            return f"Consolidation status: {job.status}"

        return "Usage: /memory consolidate [--dry-run]"

    registry.register(SlashCommand("memory", "Memory consolidation commands", memory_handler))

    # ------------------------------------------------------------------ #
    # /session fork | forks | diff                                        #
    # ------------------------------------------------------------------ #

    async def session_handler(args: str) -> str:
        from lidco.memory.session_fork import SessionForkManager

        if "fork_manager" not in _state:
            _state["fork_manager"] = SessionForkManager()

        mgr: SessionForkManager = _state["fork_manager"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "fork":
            # Parse: fork <title> [--from-turn N]
            from_turn = None
            title = rest
            if "--from-turn" in rest:
                tparts = rest.split("--from-turn")
                title = tparts[0].strip()
                try:
                    from_turn = int(tparts[1].strip().split()[0])
                except (IndexError, ValueError):
                    from_turn = None

            if not title:
                return "Usage: /session fork <title> [--from-turn N]"

            turns = list(_state.get("session_turns", []))  # type: ignore[arg-type]
            fork = mgr.create("current", title, turns, branch_point_turn=from_turn)
            return f"Fork created: {fork.fork_id}  title={fork.title!r}  turns={len(fork.turns)}"

        if sub == "forks":
            forks = mgr.list_all()
            if not forks:
                return "No forks. Use /session fork <title> to create one."
            lines = [f"Forks ({len(forks)}):"]
            for f in forks:
                lines.append(f"  {f.fork_id}  {f.title!r}  turns={len(f.turns)}")
            return "\n".join(lines)

        if sub == "diff":
            ids = rest.strip().split()
            if len(ids) < 2:
                return "Usage: /session diff <fork_id_a> <fork_id_b>"
            try:
                diff = mgr.diff(ids[0], ids[1])
            except KeyError as exc:
                return f"Fork not found: {exc}"
            return (
                f"Fork diff: common prefix={diff.common_prefix_turns}  "
                f"added={diff.added}  removed={diff.removed}"
            )

        return "Usage: /session [fork <title> | forks | diff <a> <b>]"

    registry.register(SlashCommand("session", "Session fork and diff commands", session_handler))

    # ------------------------------------------------------------------ #
    # /transcript search | next | prev                                    #
    # ------------------------------------------------------------------ #

    async def transcript_handler(args: str) -> str:
        from lidco.memory.transcript_search import TranscriptSearchIndex, Navigator

        if "transcript_index" not in _state:
            turns = list(_state.get("session_turns", []))  # type: ignore[arg-type]
            _state["transcript_index"] = TranscriptSearchIndex(turns)
        if "transcript_nav" not in _state:
            _state["transcript_nav"] = Navigator()

        idx: TranscriptSearchIndex = _state["transcript_index"]  # type: ignore[assignment]
        nav: Navigator = _state["transcript_nav"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "search":
            if not rest:
                results = idx.search("")
                return f"0 matches."
            results = idx.search(rest)
            nav.load(results)
            if results.count == 0:
                return f"0 matches for '{rest}'."
            return f"{results.count} match(es) for '{rest}'. Use /transcript next/prev to navigate."

        if sub == "next":
            if not nav.has_results():
                return "No search results. Use /transcript search <query> first."
            match = nav.next()
            pos, total = nav.position()
            if match is None:
                return "End of results."
            return f"[{pos + 1}/{total}] Turn {match.turn_index}: {match.snippet}"

        if sub == "prev":
            if not nav.has_results():
                return "No search results. Use /transcript search <query> first."
            match = nav.prev()
            pos, total = nav.position()
            if match is None:
                return "Start of results."
            return f"[{pos + 1}/{total}] Turn {match.turn_index}: {match.snippet}"

        return "Usage: /transcript [search <query> | next | prev]"

    registry.register(SlashCommand("transcript", "Search conversation transcript", transcript_handler))

    # ------------------------------------------------------------------ #
    # /summary show | update                                              #
    # ------------------------------------------------------------------ #

    async def summary_handler(args: str) -> str:
        from lidco.memory.session_summarizer import SessionSummarizer

        if "summarizer" not in _state:
            _state["summarizer"] = SessionSummarizer(summarize_fn=None, max_turns_before_summarize=20)

        summ: SessionSummarizer = _state["summarizer"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "show":
            last = summ.get_last_summary()
            if last is None:
                return "No summary available. Use /summary update."
            return f"Summary (through turn {last.covered_through_turn}):\n{last.summary_text}"

        if sub == "update":
            turns = list(_state.get("session_turns", []))  # type: ignore[arg-type]
            record = summ.update(turns, force=True)
            if record is None:
                return "Summary updated (no summarize_fn configured)."
            return f"Summary updated. Covered through turn {record.covered_through_turn}."

        return "Usage: /summary [show | update]"

    registry.register(SlashCommand("summary", "Session summary commands", summary_handler))
