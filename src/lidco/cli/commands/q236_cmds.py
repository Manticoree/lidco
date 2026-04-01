"""Q236 CLI commands: /teleport-export, /teleport-import, /share, /share-list."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q236 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    _state: dict[str, object] = {}

    # ------------------------------------------------------------------
    # /teleport-export
    # ------------------------------------------------------------------

    async def teleport_export_handler(args: str) -> str:
        from lidco.teleport.serializer import SessionSerializer

        parts = args.strip().split(maxsplit=1)
        session_id = parts[0] if parts else "default"
        message_text = parts[1] if len(parts) > 1 else ""
        messages: list[dict] = []
        if message_text:
            messages = [{"role": "user", "content": message_text}]
        serializer = SessionSerializer()
        snapshot = serializer.serialize(session_id, messages)
        data = serializer.to_json(snapshot)
        compressed = serializer.compress(data)
        return (
            f"Exported session {session_id} | "
            f"{len(snapshot.messages)} messages | "
            f"{len(data)} bytes JSON | {len(compressed)} bytes compressed"
        )

    # ------------------------------------------------------------------
    # /teleport-import
    # ------------------------------------------------------------------

    async def teleport_import_handler(args: str) -> str:
        from lidco.teleport.importer import SessionImporter

        text = args.strip()
        if not text:
            return "Usage: /teleport-import <json-data>"
        importer = SessionImporter()
        import json
        try:
            snapshot_data = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"
        result = importer.import_snapshot(snapshot_data)
        return importer.summary(result)

    # ------------------------------------------------------------------
    # /share
    # ------------------------------------------------------------------

    async def share_handler(args: str) -> str:
        from lidco.teleport.share import ShareManager

        mgr: ShareManager | None = _state.get("share_mgr")  # type: ignore[assignment]
        if mgr is None:
            mgr = ShareManager()
            _state["share_mgr"] = mgr
        parts = args.strip().split(maxsplit=1)
        session_id = parts[0] if parts else "default"
        content = parts[1] if len(parts) > 1 else ""
        anonymize = "--anon" in content
        if anonymize:
            content = content.replace("--anon", "").strip()
        link = mgr.create_share(session_id, content, anonymize=anonymize)
        return f"Share created: {link.id} | session={link.session_id} | anonymized={link.anonymized}"

    # ------------------------------------------------------------------
    # /share-list
    # ------------------------------------------------------------------

    async def share_list_handler(args: str) -> str:
        from lidco.teleport.share import ShareManager

        mgr: ShareManager | None = _state.get("share_mgr")  # type: ignore[assignment]
        if mgr is None:
            return "No shares created yet."
        return mgr.summary()

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("teleport-export", "Export session to portable format", teleport_export_handler))
    registry.register(SlashCommand("teleport-import", "Import a serialized session", teleport_import_handler))
    registry.register(SlashCommand("share", "Create a shareable session link", share_handler))
    registry.register(SlashCommand("share-list", "List active session shares", share_list_handler))
