"""Q241 CLI commands: /session-save, /session-load, /resume, /session-gc."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q241 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /session-save [id]
    # ------------------------------------------------------------------

    async def session_save_handler(args: str) -> str:
        import uuid

        from lidco.session.persister import SessionPersister

        parts = args.strip().split(maxsplit=1)
        session_id = parts[0] if parts and parts[0] else str(uuid.uuid4())

        persister = SessionPersister()
        try:
            sid = persister.save(session_id, messages=[], config=None)
            return f"Session saved: {sid}"
        finally:
            persister.close()

    # ------------------------------------------------------------------
    # /session-load <id>
    # ------------------------------------------------------------------

    async def session_load_handler(args: str) -> str:
        from lidco.session.loader import SessionLoader

        session_id = args.strip()
        if not session_id:
            return "Usage: /session-load <session-id>"

        loader = SessionLoader()
        try:
            session = loader.load(session_id)
            if session is None:
                return f"Session '{session_id}' not found."
            msg_count = len(session.get("messages") or [])
            return (
                f"Loaded session '{session_id}' "
                f"({msg_count} messages, created {session.get('created_at', '?')})"
            )
        finally:
            loader.close()

    # ------------------------------------------------------------------
    # /resume [id]
    # ------------------------------------------------------------------

    async def resume_handler(args: str) -> str:
        from lidco.session.loader import SessionLoader
        from lidco.session.persister import SessionPersister
        from lidco.session.resume_manager import ResumeManager

        persister = SessionPersister()
        loader = SessionLoader()
        manager = ResumeManager(persister, loader)
        try:
            session_id = args.strip()
            if session_id:
                session = manager.resume(session_id)
                if session is None:
                    return f"Session '{session_id}' not found."
                return manager.create_summary(session["id"])

            # No id — resume last session
            session = manager.get_last_session()
            if session is None:
                return "No sessions to resume."
            resumed = manager.resume(session["id"])
            if resumed is None:
                return "Failed to resume last session."
            return manager.create_summary(resumed["id"])
        finally:
            persister.close()
            loader.close()

    # ------------------------------------------------------------------
    # /session-gc [--dry-run]
    # ------------------------------------------------------------------

    async def session_gc_handler(args: str) -> str:
        from lidco.session.gc import SessionGarbageCollector
        from lidco.session.persister import SessionPersister

        dry = "--dry-run" in args
        persister = SessionPersister()
        gc = SessionGarbageCollector(persister)
        gc.set_retention(days=30, max_count=100)
        try:
            if dry:
                result = gc.dry_run()
                return (
                    f"Dry run: would delete {result.deleted_count} session(s), "
                    f"freeing ~{result.freed_bytes} bytes."
                )
            result = gc.collect()
            return (
                f"GC complete: deleted {result.deleted_count} session(s), "
                f"freed ~{result.freed_bytes} bytes."
            )
        finally:
            persister.close()

    registry.register(SlashCommand("session-save", "Save current session", session_save_handler))
    registry.register(SlashCommand("session-load", "Load a saved session", session_load_handler))
    registry.register(SlashCommand("resume", "Resume last or specified session", resume_handler))
    registry.register(SlashCommand("session-gc", "Garbage collect old sessions", session_gc_handler))
