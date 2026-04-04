"""Q284 CLI commands — /episodic-memory, /procedural-memory, /semantic-memory, /memory-retrieve

Registered via register_q284_commands(registry).
"""
from __future__ import annotations

import shlex

# Module-level state shared across handlers.
_state: dict = {}


def _get_episodic():
    if "episodic" not in _state:
        from lidco.agent_memory.episodic import EpisodicMemory
        _state["episodic"] = EpisodicMemory()
    return _state["episodic"]


def _get_procedural():
    if "procedural" not in _state:
        from lidco.agent_memory.procedural import ProceduralMemory
        _state["procedural"] = ProceduralMemory()
    return _state["procedural"]


def _get_semantic():
    if "semantic" not in _state:
        from lidco.agent_memory.semantic import SemanticMemory2
        _state["semantic"] = SemanticMemory2()
    return _state["semantic"]


def _get_retrieval():
    if "retrieval" not in _state:
        from lidco.agent_memory.retrieval import MemoryRetrieval
        r = MemoryRetrieval()
        r.add_source("episodic", _get_episodic())
        r.add_source("procedural", _get_procedural())
        r.add_source("semantic", _get_semantic())
        _state["retrieval"] = r
    return _state["retrieval"]


def register_q284_commands(registry) -> None:
    """Register Q284 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /episodic-memory [record <desc> <outcome> <strategy> | search <q> | recent [n] | by-outcome <outcome>]
    # ------------------------------------------------------------------
    async def episodic_memory_handler(args: str) -> str:
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "recent"
        mem = _get_episodic()

        if subcmd == "record":
            if len(parts) < 4:
                return "Usage: /episodic-memory record <description> <outcome> <strategy>"
            ep = mem.record({
                "description": parts[1],
                "outcome": parts[2],
                "strategy": parts[3],
            })
            return f"Recorded episode {ep.id}: {ep.description} ({ep.outcome})"

        if subcmd == "search":
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not query:
                return "Usage: /episodic-memory search <query>"
            results = mem.search(query)
            if not results:
                return "No matching episodes found."
            lines = [f"Found {len(results)} episode(s):"]
            for ep in results:
                lines.append(f"  [{ep.outcome}] {ep.description} — {ep.strategy}")
            return "\n".join(lines)

        if subcmd == "recent":
            n = int(parts[1]) if len(parts) > 1 else 5
            episodes = mem.recent(n)
            if not episodes:
                return "No episodes recorded."
            lines = [f"Recent {len(episodes)} episode(s):"]
            for ep in episodes:
                lines.append(f"  [{ep.outcome}] {ep.description}")
            return "\n".join(lines)

        if subcmd == "by-outcome":
            if len(parts) < 2:
                return "Usage: /episodic-memory by-outcome <success|failure>"
            outcome = parts[1]
            episodes = mem.by_outcome(outcome)
            if not episodes:
                return f"No {outcome} episodes found."
            lines = [f"{len(episodes)} {outcome} episode(s):"]
            for ep in episodes:
                lines.append(f"  {ep.description} — {ep.strategy}")
            return "\n".join(lines)

        return (
            "Usage: /episodic-memory <subcommand>\n"
            "  record <desc> <outcome> <strategy>  record episode\n"
            "  search <query>                       search episodes\n"
            "  recent [n]                           recent episodes\n"
            "  by-outcome <success|failure>         filter by outcome"
        )

    # ------------------------------------------------------------------
    # /procedural-memory [record <type> <name> <steps...> | find <type> | update <id> <success|failure> | generalize]
    # ------------------------------------------------------------------
    async def procedural_memory_handler(args: str) -> str:
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "generalize"
        mem = _get_procedural()

        if subcmd == "record":
            if len(parts) < 4:
                return "Usage: /procedural-memory record <task_type> <name> <step1> [step2 ...]"
            proc = mem.record({
                "task_type": parts[1],
                "name": parts[2],
                "steps": parts[3:],
            })
            return f"Recorded procedure {proc.id}: {proc.name} ({len(proc.steps)} steps)"

        if subcmd == "find":
            if len(parts) < 2:
                return "Usage: /procedural-memory find <task_type>"
            results = mem.find(parts[1])
            if not results:
                return "No matching procedures found."
            lines = [f"Found {len(results)} procedure(s):"]
            for p in results:
                lines.append(f"  {p.name} (rate: {p.success_rate:.0%}, steps: {len(p.steps)})")
            return "\n".join(lines)

        if subcmd == "update":
            if len(parts) < 3:
                return "Usage: /procedural-memory update <proc_id> <success|failure>"
            try:
                success = parts[2] == "success"
                proc = mem.update_success_rate(parts[1], success)
                return f"Updated {proc.name}: rate={proc.success_rate:.0%}"
            except KeyError as exc:
                return str(exc)

        if subcmd == "generalize":
            results = mem.generalize()
            if not results:
                return "No generalizable procedures yet."
            lines = [f"{len(results)} generalizable procedure(s):"]
            for p in results:
                lines.append(f"  {p.name} (rate: {p.success_rate:.0%})")
            return "\n".join(lines)

        return (
            "Usage: /procedural-memory <subcommand>\n"
            "  record <type> <name> <steps...>   record procedure\n"
            "  find <task_type>                   find procedures\n"
            "  update <id> <success|failure>      update success rate\n"
            "  generalize                         list reliable procedures"
        )

    # ------------------------------------------------------------------
    # /semantic-memory [add <content> [category] | query <q> | decay <days> | list]
    # ------------------------------------------------------------------
    async def semantic_memory_handler(args: str) -> str:
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "list"
        mem = _get_semantic()

        if subcmd == "add":
            if len(parts) < 2:
                return "Usage: /semantic-memory add <content> [category]"
            category = parts[2] if len(parts) > 2 else "general"
            fact = mem.add_fact({"content": parts[1], "category": category})
            return f"Added fact {fact.id}: {fact.content} [{fact.category}]"

        if subcmd == "query":
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not query:
                return "Usage: /semantic-memory query <query>"
            results = mem.query(query)
            if not results:
                return "No matching facts found."
            lines = [f"Found {len(results)} fact(s):"]
            for f in results:
                lines.append(f"  [{f.category}] {f.content} (conf: {f.confidence:.2f})")
            return "\n".join(lines)

        if subcmd == "decay":
            if len(parts) < 2:
                return "Usage: /semantic-memory decay <days>"
            removed = mem.decay(int(parts[1]))
            return f"Removed {removed} expired fact(s)."

        if subcmd == "list":
            all_facts = mem.facts()
            if not all_facts:
                return "No facts stored."
            lines = [f"{len(all_facts)} fact(s):"]
            for f in all_facts:
                lines.append(f"  [{f.category}] {f.content}")
            return "\n".join(lines)

        return (
            "Usage: /semantic-memory <subcommand>\n"
            "  add <content> [category]  add a fact\n"
            "  query <query>             search facts\n"
            "  decay <days>              remove old facts\n"
            "  list                      list all facts"
        )

    # ------------------------------------------------------------------
    # /memory-retrieve <query> [top_k]
    # ------------------------------------------------------------------
    async def memory_retrieve_handler(args: str) -> str:
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /memory-retrieve <query> [top_k]"

        query = parts[0]
        top_k = int(parts[1]) if len(parts) > 1 else 5
        retrieval = _get_retrieval()
        results = retrieval.retrieve(query, top_k=top_k)
        if not results:
            return "No relevant memories found."
        lines = [f"Top {len(results)} result(s):"]
        for r in results:
            lines.append(f"  [{r.source}] {r.content} (score: {r.score:.2f})")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("episodic-memory", "Manage episodic agent memory", episodic_memory_handler))
    registry.register(SlashCommand("procedural-memory", "Manage procedural agent memory", procedural_memory_handler))
    registry.register(SlashCommand("semantic-memory", "Manage semantic agent memory", semantic_memory_handler))
    registry.register(SlashCommand("memory-retrieve", "Retrieve across all memory sources", memory_retrieve_handler))
