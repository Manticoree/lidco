"""Q217 CLI commands: /collab, /review, /pair-session, /knowledge."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q217 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /collab
    # ------------------------------------------------------------------

    async def collab_handler(args: str) -> str:
        from lidco.collab.shared_workspace import SharedWorkspace

        room_name = args.strip()
        if not room_name:
            return "Usage: /collab <room_name>"
        ws = SharedWorkspace(room_id=room_name, name=room_name)
        ws.add_participant("host", "Host", "owner")
        return ws.summary()

    # ------------------------------------------------------------------
    # /review
    # ------------------------------------------------------------------

    async def review_handler(args: str) -> str:
        from lidco.collab.review_integration import ReviewIntegration

        stripped = args.strip()
        if not stripped:
            return "Usage: /review <file:line> <comment>"
        parts = stripped.split(None, 1)
        loc = parts[0]
        comment = parts[1] if len(parts) > 1 else ""
        if ":" not in loc:
            return "Usage: /review <file:line> <comment>"
        file_path, line_str = loc.rsplit(":", 1)
        try:
            line = int(line_str)
        except ValueError:
            return "Line must be a number."
        ri = ReviewIntegration()
        ri.add_comment(file_path, line, "user", comment)
        return ri.summary()

    # ------------------------------------------------------------------
    # /pair-session
    # ------------------------------------------------------------------

    async def pair_session_handler(args: str) -> str:
        from lidco.collab.pair_session import PairSession

        stripped = args.strip()
        if not stripped:
            return "Usage: /pair-session <create|join|swap|end> [args]"
        parts = stripped.split(None, 1)
        action = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        if action == "create":
            name = rest or "pair-1"
            session = PairSession(session_id=name, creator="user")
            return session.summary()
        elif action == "join":
            name = rest or "guest"
            session = PairSession(session_id="pair-1", creator="host")
            session.join(name, name)
            return session.summary()
        elif action == "swap":
            session = PairSession(session_id="pair-1", creator="user")
            session.join("partner", "partner")
            session.swap_roles()
            return session.summary()
        elif action == "end":
            session = PairSession(session_id="pair-1", creator="user")
            session.end()
            return session.summary()
        else:
            return "Unknown action. Use: create, join, swap, end"

    # ------------------------------------------------------------------
    # /knowledge
    # ------------------------------------------------------------------

    async def knowledge_handler(args: str) -> str:
        from lidco.collab.knowledge_share import KnowledgeShare

        stripped = args.strip()
        if not stripped:
            return "Usage: /knowledge <add|search|top> [args]"
        parts = stripped.split(None, 1)
        action = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        ks = KnowledgeShare()
        if action == "add":
            if not rest:
                return "Usage: /knowledge add <title> | <content>"
            if "|" in rest:
                title, content = rest.split("|", 1)
            else:
                title, content = rest, ""
            snippet = ks.add_snippet(title.strip(), content.strip(), "user")
            return f"Added snippet {snippet.id}: {snippet.title}"
        elif action == "search":
            if not rest:
                return "Usage: /knowledge search <query>"
            results = ks.search(rest)
            if not results:
                return "No snippets found."
            return "\n".join(f"- {s.title} ({s.id})" for s in results)
        elif action == "top":
            results = ks.top_snippets()
            if not results:
                return "No snippets yet."
            return "\n".join(f"- {s.title} [{s.upvotes} votes]" for s in results)
        else:
            return "Unknown action. Use: add, search, top"

    registry.register(
        SlashCommand("collab", "Create shared workspace room", collab_handler)
    )
    registry.register(
        SlashCommand("review", "Add inline review comment", review_handler)
    )
    registry.register(
        SlashCommand("pair-session", "Manage pair programming session", pair_session_handler)
    )
    registry.register(
        SlashCommand("knowledge", "Team knowledge sharing", knowledge_handler)
    )
