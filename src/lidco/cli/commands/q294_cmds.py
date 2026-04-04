"""
Q294 CLI commands — /notion, /notion-sync, /notion-kb, /notion-meeting

Registered via register_q294_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q294_commands(registry) -> None:
    """Register Q294 slash commands onto the given registry."""

    # shared state across commands in this session
    _state: dict[str, object] = {}

    def _get_client():
        from lidco.notion.client import NotionClient

        if "client" not in _state:
            _state["client"] = NotionClient()
        return _state["client"]

    # ------------------------------------------------------------------
    # /notion — Core Notion client operations
    # ------------------------------------------------------------------
    async def notion_handler(args: str) -> str:
        """
        Usage: /notion create <title> [content]
               /notion get <page_id>
               /notion search <query>
               /notion delete <page_id>
               /notion databases
        """
        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /notion <subcommand>\n"
                "  create <title> [content]  create a page\n"
                "  get <page_id>             get a page\n"
                "  search <query>            search pages\n"
                "  delete <page_id>          delete a page\n"
                "  databases                 list databases"
            )

        client = _get_client()
        subcmd = parts[0].lower()

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: title required. Usage: /notion create <title> [content]"
            title = parts[1]
            content = parts[2] if len(parts) > 2 else ""
            try:
                page = client.create_page(None, title, content)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Page created: {page.id} — {page.title}"

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: page_id required."
            try:
                page = client.get_page(parts[1])
            except KeyError:
                return f"Page not found: {parts[1]}"
            return f"[{page.id}] {page.title}\n{page.content}" if page.content else f"[{page.id}] {page.title}"

        if subcmd == "search":
            if len(parts) < 2:
                return "Error: query required."
            results = client.search(parts[1])
            if not results:
                return "No pages found."
            return "\n".join(f"  [{p.id}] {p.title}" for p in results)

        if subcmd == "delete":
            if len(parts) < 2:
                return "Error: page_id required."
            deleted = client.delete_page(parts[1])
            return f"Page deleted: {parts[1]}" if deleted else f"Page not found: {parts[1]}"

        if subcmd == "databases":
            dbs = client.list_databases()
            if not dbs:
                return "No databases."
            return "\n".join(f"  [{d.id}] {d.title}" for d in dbs)

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("notion", "Notion page operations", notion_handler)

    # ------------------------------------------------------------------
    # /notion-sync — Sync markdown files with Notion
    # ------------------------------------------------------------------
    async def notion_sync_handler(args: str) -> str:
        """
        Usage: /notion-sync file <path>
               /notion-sync dir <directory>
               /notion-sync status <path>
        """
        from lidco.notion.doc_sync import DocSync

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /notion-sync <subcommand>\n"
                "  file <path>       sync a single file\n"
                "  dir <directory>   sync all .md files in directory\n"
                "  status <path>     show last sync time"
            )

        if "doc_sync" not in _state:
            _state["doc_sync"] = DocSync(_get_client())
        ds: DocSync = _state["doc_sync"]  # type: ignore[assignment]
        subcmd = parts[0].lower()

        if subcmd == "file":
            if len(parts) < 2:
                return "Error: path required."
            try:
                result = ds.sync_file(parts[1])
            except FileNotFoundError as exc:
                return f"Error: {exc}"
            return f"[{result.status}] {result.path} — {result.message}"

        if subcmd == "dir":
            if len(parts) < 2:
                return "Error: directory required."
            try:
                results = ds.sync_all(parts[1])
            except NotADirectoryError as exc:
                return f"Error: {exc}"
            if not results:
                return "No .md files found."
            lines = [f"  [{r.status}] {r.path}" for r in results]
            return f"Synced {len(results)} file(s):\n" + "\n".join(lines)

        if subcmd == "status":
            if len(parts) < 2:
                return "Error: path required."
            ts = ds.last_sync(parts[1])
            if ts == 0.0:
                return f"Never synced: {parts[1]}"
            return f"Last sync: {ts:.1f}"

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("notion-sync", "Sync markdown files with Notion", notion_sync_handler)

    # ------------------------------------------------------------------
    # /notion-kb — Knowledge base queries
    # ------------------------------------------------------------------
    async def notion_kb_handler(args: str) -> str:
        """
        Usage: /notion-kb add <title> <content>
               /notion-kb query <question>
               /notion-kb context <question> [--max-tokens N]
               /notion-kb size
        """
        from lidco.notion.knowledge import KnowledgeBase

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /notion-kb <subcommand>\n"
                "  add <title> <content>   add a document\n"
                "  query <question>        search documents\n"
                "  context <question>      build context string\n"
                "  size                    show index size"
            )

        if "kb" not in _state:
            _state["kb"] = KnowledgeBase()
        kb: KnowledgeBase = _state["kb"]  # type: ignore[assignment]
        subcmd = parts[0].lower()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: title and content required."
            try:
                kb.add_doc(parts[1], parts[2])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Document added: {parts[1]}"

        if subcmd == "query":
            if len(parts) < 2:
                return "Error: question required."
            results = kb.query(parts[1])
            if not results:
                return "No matching documents."
            return "\n".join(f"  {d.title}" for d in results)

        if subcmd == "context":
            if len(parts) < 2:
                return "Error: question required."
            max_tokens = 500
            i = 2
            while i < len(parts):
                if parts[i] == "--max-tokens" and i + 1 < len(parts):
                    i += 1
                    try:
                        max_tokens = int(parts[i])
                    except ValueError:
                        pass
                i += 1
            ctx = kb.inject_context(parts[1], max_tokens=max_tokens)
            return ctx if ctx else "No relevant context found."

        if subcmd == "size":
            return f"Index size: {kb.index_size()} document(s)"

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("notion-kb", "Notion knowledge base queries", notion_kb_handler)

    # ------------------------------------------------------------------
    # /notion-meeting — Meeting notes management
    # ------------------------------------------------------------------
    async def notion_meeting_handler(args: str) -> str:
        """
        Usage: /notion-meeting create <title> [attendee1,attendee2,...]
               /notion-meeting notes <id> <text>
               /notion-meeting actions <id>
               /notion-meeting assign <id> <item_text> <person>
               /notion-meeting list
        """
        from lidco.notion.meetings import MeetingNotes

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /notion-meeting <subcommand>\n"
                "  create <title> [attendees]  create meeting\n"
                "  notes <id> <text>           add notes\n"
                "  actions <id>                extract action items\n"
                "  assign <id> <item> <person> assign follow-up\n"
                "  list                        list meetings"
            )

        if "meetings" not in _state:
            _state["meetings"] = MeetingNotes()
        mn: MeetingNotes = _state["meetings"]  # type: ignore[assignment]
        subcmd = parts[0].lower()

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: title required."
            title = parts[1]
            attendees = parts[2].split(",") if len(parts) > 2 else []
            try:
                meeting = mn.create(title, attendees)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Meeting created: {meeting.id} — {meeting.title}"

        if subcmd == "notes":
            if len(parts) < 3:
                return "Error: id and text required."
            try:
                mn.add_notes(parts[1], parts[2])
            except KeyError:
                return f"Meeting not found: {parts[1]}"
            return "Notes added."

        if subcmd == "actions":
            if len(parts) < 2:
                return "Error: meeting id required."
            try:
                items = mn.extract_action_items(parts[1])
            except KeyError:
                return f"Meeting not found: {parts[1]}"
            if not items:
                return "No action items found."
            return "\n".join(f"  - {ai.text}" for ai in items)

        if subcmd == "assign":
            if len(parts) < 4:
                return "Error: id, item text, and person required."
            try:
                ok = mn.assign_followup(parts[1], parts[2], parts[3])
            except KeyError:
                return f"Meeting not found: {parts[1]}"
            return f"Assigned to {parts[3]}." if ok else "Action item not found."

        if subcmd == "list":
            meetings = mn.list_meetings()
            if not meetings:
                return "No meetings."
            return "\n".join(f"  [{m.id}] {m.title}" for m in meetings)

        return f"Unknown subcommand '{subcmd}'."

    registry.register_async("notion-meeting", "Meeting notes management", notion_meeting_handler)
