"""Q111 CLI commands: /memory /checkpoint."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q111 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /memory                                                              #
    # ------------------------------------------------------------------ #

    async def memory_handler(args: str) -> str:
        from lidco.memory.conversation_extractor import (
            ConversationMemoryExtractor,
            ExtractedFact,
        )
        from lidco.memory.approval_queue import MemoryApprovalQueue, FactNotFoundError
        from lidco.memory.injector import MemoryInjector

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_queue() -> MemoryApprovalQueue:
            if "approval_queue" not in _state:
                _state["approval_queue"] = MemoryApprovalQueue()
            return _state["approval_queue"]  # type: ignore[return-value]

        if sub == "extract":
            if not rest:
                return "Usage: /memory extract <text>"
            extractor = ConversationMemoryExtractor()
            transcript = [{"role": "user", "content": rest}]
            facts = extractor.extract(transcript)
            if not facts:
                return "No facts extracted."
            queue = _get_queue()
            lines = [f"Extracted {len(facts)} fact(s):"]
            for f in facts:
                fid = queue.add(f)
                lines.append(
                    f"  [{fid}] ({f.confidence:.1f}) {f.content}"
                    + (f"  tags: {f.tags}" if f.tags else "")
                )
            return "\n".join(lines)

        if sub == "approve":
            if not rest:
                return "Usage: /memory approve <id>"
            queue = _get_queue()
            try:
                fact = queue.approve(rest.strip())
                return f"Approved: {fact.content}"
            except FactNotFoundError:
                return f"Not found: {rest.strip()}"

        if sub == "reject":
            if not rest:
                return "Usage: /memory reject <id>"
            queue = _get_queue()
            try:
                queue.reject(rest.strip())
                return f"Rejected: {rest.strip()}"
            except FactNotFoundError:
                return f"Not found: {rest.strip()}"

        if sub == "list":
            queue = _get_queue()
            pending = queue.list_pending()
            if not pending:
                return "No pending facts."
            lines = [f"Pending facts ({len(pending)}):"]
            for p in pending:
                lines.append(
                    f"  [{p.id}] ({p.fact.confidence:.1f}) {p.fact.content}"
                )
            return "\n".join(lines)

        if sub == "inject":
            injector = MemoryInjector()
            result = injector.compose()
            if not result.prompt_block:
                return "No memories to inject."
            return (
                f"Facts included: {result.facts_included}\n"
                f"Facts dropped: {result.facts_dropped}\n"
                f"Tokens used: {result.tokens_used}\n"
                f"---\n{result.prompt_block}"
            )

        return (
            "Usage: /memory <sub>\n"
            "  extract <text>  -- extract facts from text\n"
            "  approve <id>    -- approve a pending fact\n"
            "  reject <id>     -- reject a pending fact\n"
            "  list            -- list pending facts\n"
            "  inject          -- show memory injection preview"
        )

    # ------------------------------------------------------------------ #
    # /checkpoint                                                          #
    # ------------------------------------------------------------------ #

    async def checkpoint_handler(args: str) -> str:
        from lidco.memory.session_checkpoint import (
            SessionCheckpointStore,
            CheckpointNotFoundError,
        )

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_store() -> SessionCheckpointStore:
            if "checkpoint_store" not in _state:
                _state["checkpoint_store"] = SessionCheckpointStore()
            return _state["checkpoint_store"]  # type: ignore[return-value]

        if sub == "save":
            if not rest:
                return "Usage: /checkpoint save <label>"
            store = _get_store()
            cp_id = store.save(label=rest.strip(), messages=[], file_refs=[])
            return f"Checkpoint saved: {cp_id} ({rest.strip()})"

        if sub == "list":
            store = _get_store()
            cps = store.list()
            if not cps:
                return "No checkpoints."
            lines = [f"Checkpoints ({len(cps)}):"]
            for cp in cps:
                lines.append(
                    f"  [{cp.id}] {cp.label}  ({len(cp.messages)} msgs, {cp.created_at})"
                )
            return "\n".join(lines)

        if sub == "restore":
            if not rest:
                return "Usage: /checkpoint restore <id>"
            store = _get_store()
            try:
                cp = store.restore(rest.strip())
                return (
                    f"Restored checkpoint: {cp.label}\n"
                    f"Messages: {len(cp.messages)}\n"
                    f"Files: {len(cp.file_refs)}"
                )
            except CheckpointNotFoundError:
                return f"Not found: {rest.strip()}"

        if sub == "diff":
            tokens = rest.strip().split()
            if len(tokens) < 2:
                return "Usage: /checkpoint diff <id1> <id2>"
            store = _get_store()
            try:
                d = store.diff(tokens[0], tokens[1])
                return (
                    f"Messages added: {d.messages_added}\n"
                    f"Messages removed: {d.messages_removed}\n"
                    f"Files changed: {d.files_changed}"
                )
            except CheckpointNotFoundError as e:
                return f"Error: {e}"

        return (
            "Usage: /checkpoint <sub>\n"
            "  save <label>       -- save a checkpoint\n"
            "  list               -- list all checkpoints\n"
            "  restore <id>       -- restore a checkpoint\n"
            "  diff <id1> <id2>   -- diff two checkpoints"
        )

    registry.register(SlashCommand("memory", "Memory extraction & approval", memory_handler))
    registry.register(SlashCommand("checkpoint", "Session checkpoints", checkpoint_handler))
