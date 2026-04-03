"""
Q243 CLI commands — /context-segments, /virtual-memory, /defrag, /context-schedule

Registered via register_q243_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q243_commands(registry) -> None:
    """Register Q243 slash commands onto the given registry."""

    _seg_state: dict[str, object] = {}
    _vm_state: dict[str, object] = {}
    _defrag_state: dict[str, object] = {}
    _sched_state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /context-segments
    # ------------------------------------------------------------------
    async def context_segments_handler(args: str) -> str:
        """
        Usage: /context-segments list
               /context-segments create <name> <budget>
               /context-segments add <name> <entry>
               /context-segments resize <name> <budget>
               /context-segments stats
        """
        from lidco.context.segments import ContextSegments

        if "segs" not in _seg_state:
            _seg_state["segs"] = ContextSegments.with_defaults()

        segs: ContextSegments = _seg_state["segs"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /context-segments <subcommand>\n"
                "  list                  list all segments\n"
                "  create <name> <budget> create a segment\n"
                "  add <name> <entry>    add entry to segment\n"
                "  resize <name> <budget> resize segment budget\n"
                "  stats                 show stats"
            )

        if subcmd == "list":
            segs_list = segs.list_segments()
            if not segs_list:
                return "No segments defined."
            lines = [f"  {s.name}: {s.used}/{s.budget} tokens, {len(s.entries)} entries" for s in segs_list]
            return "Segments:\n" + "\n".join(lines)

        if subcmd == "create" and len(parts) >= 3:
            name = parts[1]
            try:
                budget = int(parts[2])
            except ValueError:
                return "Budget must be an integer."
            try:
                segs.create_segment(name, budget)
            except ValueError as exc:
                return str(exc)
            return f"Created segment '{name}' with budget {budget}."

        if subcmd == "add" and len(parts) >= 3:
            name = parts[1]
            entry = " ".join(parts[2:])
            ok = segs.add_to_segment(name, entry)
            return f"Added to '{name}'." if ok else f"Failed to add to '{name}' (over budget or missing)."

        if subcmd == "resize" and len(parts) >= 3:
            name = parts[1]
            try:
                budget = int(parts[2])
            except ValueError:
                return "Budget must be an integer."
            ok = segs.resize(name, budget)
            return f"Resized '{name}' to {budget}." if ok else f"Segment '{name}' not found."

        if subcmd == "stats":
            s = segs.stats()
            return (
                f"Segments: {s['segment_count']}, "
                f"Total budget: {s['total_budget']}, "
                f"Total used: {s['total_used']}"
            )

        return f"Unknown subcommand '{subcmd}'. Use list/create/add/resize/stats."

    registry.register_async("context-segments", "Manage context window segments", context_segments_handler)

    # ------------------------------------------------------------------
    # /virtual-memory
    # ------------------------------------------------------------------
    async def virtual_memory_handler(args: str) -> str:
        """
        Usage: /virtual-memory add <id> <content>
               /virtual-memory access <id>
               /virtual-memory evict
               /virtual-memory working-set
               /virtual-memory stats
        """
        from lidco.context.virtual_memory import VirtualMemory

        if "vm" not in _vm_state:
            _vm_state["vm"] = VirtualMemory()

        vm: VirtualMemory = _vm_state["vm"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /virtual-memory <subcommand>\n"
                "  add <id> <content>  add a page\n"
                "  access <id>         access a page\n"
                "  evict               evict LRU page\n"
                "  working-set         show in-memory pages\n"
                "  stats               show stats"
            )

        if subcmd == "add" and len(parts) >= 3:
            pid = parts[1]
            content = " ".join(parts[2:])
            vm.add_page(pid, content)
            return f"Added page '{pid}'."

        if subcmd == "access" and len(parts) >= 2:
            pid = parts[1]
            content = vm.access(pid)
            if content is None:
                return f"Page '{pid}' not found."
            return f"Page '{pid}': {content[:200]}"

        if subcmd == "evict":
            evicted = vm.evict_lru()
            return f"Evicted page '{evicted}'." if evicted else "No pages to evict."

        if subcmd == "working-set":
            ws = vm.working_set()
            return f"Working set: {', '.join(ws)}" if ws else "Working set is empty."

        if subcmd == "stats":
            s = vm.stats()
            return (
                f"Pages: {s['total_pages']} total, "
                f"{s['in_memory']} in memory, "
                f"{s['on_disk']} on disk"
            )

        return f"Unknown subcommand '{subcmd}'. Use add/access/evict/working-set/stats."

    registry.register_async("virtual-memory", "Virtual memory for context pages", virtual_memory_handler)

    # ------------------------------------------------------------------
    # /defrag
    # ------------------------------------------------------------------
    async def defrag_handler(args: str) -> str:
        """
        Usage: /defrag run
               /defrag compact <segment>
               /defrag stats
        """
        from lidco.context.defragmenter import ContextDefragmenter
        from lidco.context.segments import ContextSegments

        if "segs" not in _defrag_state:
            _defrag_state["segs"] = ContextSegments.with_defaults()
        if "defrag" not in _defrag_state:
            _defrag_state["defrag"] = ContextDefragmenter(_defrag_state["segs"])  # type: ignore[arg-type]

        defrag: ContextDefragmenter = _defrag_state["defrag"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /defrag <subcommand>\n"
                "  run              run full defragmentation\n"
                "  compact <seg>    compact a specific segment\n"
                "  stats            show defrag stats"
            )

        if subcmd == "run":
            result = defrag.defragment()
            return f"Defrag complete: merged={result.merged_count}, reclaimed={result.reclaimed_tokens} tokens."

        if subcmd == "compact" and len(parts) >= 2:
            seg_name = parts[1]
            reclaimed = defrag.compact(seg_name)
            return f"Compacted '{seg_name}': reclaimed {reclaimed} tokens."

        if subcmd == "stats":
            s = defrag.stats()
            return (
                f"Defrag runs: {s['defrag_count']}, "
                f"Total reclaimed: {s['total_reclaimed']}, "
                f"Segments: {s['segment_count']}"
            )

        return f"Unknown subcommand '{subcmd}'. Use run/compact/stats."

    registry.register_async("defrag", "Defragment context window segments", defrag_handler)

    # ------------------------------------------------------------------
    # /context-schedule
    # ------------------------------------------------------------------
    async def context_schedule_handler(args: str) -> str:
        """
        Usage: /context-schedule add <id> <priority> <category> <content>
               /context-schedule run <budget>
               /context-schedule remove <id>
               /context-schedule stats
        """
        from lidco.context.scheduler import ContextEntry, ContextScheduler

        if "sched" not in _sched_state:
            _sched_state["sched"] = ContextScheduler()

        sched: ContextScheduler = _sched_state["sched"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else ""

        if not subcmd:
            return (
                "Usage: /context-schedule <subcommand>\n"
                "  add <id> <priority> <category> <content>\n"
                "  run <budget>     schedule within budget\n"
                "  remove <id>      remove an entry\n"
                "  stats            show stats"
            )

        if subcmd == "add" and len(parts) >= 5:
            eid = parts[1]
            try:
                priority = int(parts[2])
            except ValueError:
                return "Priority must be an integer."
            category = parts[3]
            content = " ".join(parts[4:])
            entry = ContextEntry(
                id=eid,
                content=content,
                priority=priority,
                category=category,
                token_estimate=max(1, len(content) // 4),
            )
            sched.add(entry)
            return f"Added entry '{eid}' (priority={priority}, category={category})."

        if subcmd == "run" and len(parts) >= 2:
            try:
                budget = int(parts[1])
            except ValueError:
                return "Budget must be an integer."
            selected = sched.schedule(budget)
            if not selected:
                return "No entries fit within the budget."
            lines = [f"  {e.id}: priority={e.priority}, tokens={e.token_estimate}" for e in selected]
            return f"Scheduled {len(selected)} entries:\n" + "\n".join(lines)

        if subcmd == "remove" and len(parts) >= 2:
            eid = parts[1]
            ok = sched.remove(eid)
            return f"Removed '{eid}'." if ok else f"Entry '{eid}' not found."

        if subcmd == "stats":
            s = sched.stats()
            return (
                f"Entries: {s['entry_count']}, "
                f"Total tokens: {s['total_tokens']}, "
                f"Schedules: {s['schedule_count']}, "
                f"Preemptions: {s['preempt_count']}"
            )

        return f"Unknown subcommand '{subcmd}'. Use add/run/remove/stats."

    registry.register_async("context-schedule", "Priority-based context scheduling", context_schedule_handler)
