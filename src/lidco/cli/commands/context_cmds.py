"""Commands: context and session management."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register context and session management commands."""
    from lidco.cli.commands.registry import SlashCommand


    # ── Q41 — UX Completeness (Tasks 276–285) ────────────────────────────

    # Task 276 (merges Task 161): /compact — keep last N messages OR LLM summarize
    async def compact_handler(arg: str = "", **_: Any) -> str:
        """/compact [N | focus] — keep last N messages, or LLM-summarize with optional focus."""
        session = registry._session
        orch = getattr(session, "orchestrator", None)
        if orch is None:
            return "No active session."
        history = getattr(orch, "_conversation_history", None) or []

        # ── Numeric arg: truncate mode (Task 161 behaviour) ──────────────
        arg_stripped = arg.strip()
        if arg_stripped == "" or arg_stripped.lstrip("-").isdigit():
            if not history:
                return "История разговора пуста — нечего сжимать."
            _DEFAULT_KEEP = 6
            keep = _DEFAULT_KEEP
            if arg_stripped:
                try:
                    keep = int(arg_stripped)
                except ValueError:
                    return f"Неверный аргумент: `{arg_stripped}`. Использование: `/compact [N]` (N — количество сообщений)."
            keep = max(2, keep)
            if len(history) <= keep:
                return f"История уже короткая ({len(history)} сообщений) — нечего удалять."
            removed = len(history) - keep
            compacted = history[-keep:]
            orch.restore_history(compacted)
            return f"Оставлено {keep} сообщений, удалено {removed}."

        # ── Non-numeric arg: validate — must start with "--llm" ──────────────
        if not arg_stripped.startswith("--llm"):
            return f"Неверный аргумент: `{arg_stripped}`. Использование: `/compact [N]` или `/compact --llm [focus]`."

        # ── LLM summarisation mode (Task 276) ────────────────────────────
        if not history:
            return "Conversation history is empty — nothing to compact."
        focus_hint = arg_stripped[len("--llm"):].strip()
        system = (
            "You are a conversation summarizer. "
            "Compress the following conversation history into a concise summary "
            "that preserves ALL important decisions, code snippets, file paths, "
            "error messages, and conclusions. "
            "Output only the summary — no preamble."
        )
        if focus_hint:
            system += f" Pay special attention to: {focus_hint}."

        history_text = "\n".join(
            f"[{m.get('role','?')}]: {str(m.get('content',''))[:300]}"
            for m in history[-40:]
        )
        try:
            llm = getattr(session, "llm", None)
            if llm is None:
                return "LLM not available."
            resp = await llm.complete(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Summarize:\n\n{history_text}"},
                ],
                model=None,
                max_tokens=800,
            )
            summary = resp.content if hasattr(resp, "content") else str(resp)
            orch._conversation_history = [
                {"role": "assistant", "content": f"[Compacted history]\n\n{summary}"}
            ]
            turns_before = len(history)
            return (
                f"History compacted: {turns_before} messages → 1 summary.\n\n"
                f"**Summary:**\n{summary}"
            )
        except Exception as exc:
            return f"Compact failed: {exc}"

    registry.register(SlashCommand("compact", "Compress conversation history (N=keep last N, text=LLM summarize)", compact_handler))

    # Task 277: /context — visual token gauge
    async def context_handler(arg: str = "", **_: Any) -> str:
        """/context [tree] — visual context window usage gauge or section tree."""
        session = registry._session
        config = getattr(session, "config", None)
        budget = getattr(session, "token_budget", None)

        # Task 387: /context tree — parse context into sections with token estimates
        if arg.strip().lower() == "tree":
            import re as _re
            orch = getattr(session, "orchestrator", None)
            history = getattr(orch, "_conversation_history", []) if orch else []
            # Build a combined context string from system/assistant messages
            context_str = ""
            for m in history:
                role = m.get("role", "")
                content = str(m.get("content", ""))
                if role in ("system", "assistant"):
                    context_str += content + "\n"

            # If no history, try session context attribute
            if not context_str:
                context_str = getattr(session, "context", "") or ""

            total_limit = 128_000
            if config is not None:
                try:
                    limit_cfg = int(getattr(config.agents, "context_window", 0))
                    if limit_cfg > 0:
                        total_limit = limit_cfg
                except (TypeError, ValueError):
                    pass

            # Parse by ## headings
            sections: list[tuple[str, str]] = []
            current_title = "Preamble"
            current_body: list[str] = []
            for line in context_str.splitlines():
                m = _re.match(r"^##\s+(.+)$", line)
                if m:
                    sections.append((current_title, "\n".join(current_body)))
                    current_title = m.group(1).strip()
                    current_body = []
                else:
                    current_body.append(line)
            sections.append((current_title, "\n".join(current_body)))

            # Filter empty
            sections = [(t, b) for t, b in sections if b.strip()]

            total_chars = sum(len(b) for _, b in sections)
            total_toks = max(total_chars // 4, 1)

            try:
                from rich.tree import Tree as _Tree
                from rich.console import Console as _Con
                import io as _io
                tree = _Tree(f"[bold cyan]Context[/bold cyan] [{total_toks} tok / {total_limit // 1000}k limit]")
                for title, body in sections:
                    toks = len(body) // 4
                    pct_sec = int(toks / total_limit * 100) if total_limit else 0
                    tree.add(f"[dim]##[/dim] {title}  [yellow][{toks} tok, {pct_sec}%][/yellow]")
                buf = _io.StringIO()
                c = _Con(file=buf, highlight=False)
                c.print(tree)
                return buf.getvalue().rstrip()
            except Exception:
                lines = [f"**Context tree** ({total_toks} tokens estimated)\n"]
                for title, body in sections:
                    toks = len(body) // 4
                    lines.append(f"  ## {title}  [{toks} tok]")
                return "\n".join(lines)

        # Default: gauge view
        # Gather stats
        used = 0
        prompt_tokens = 0
        completion_tokens = 0
        total_limit = 128_000

        if budget is not None:
            stats = getattr(budget, "_stats", None)
            if stats is not None:
                used = getattr(stats, "total_tokens", 0)
                prompt_tokens = getattr(stats, "prompt_tokens", 0)
                completion_tokens = getattr(stats, "completion_tokens", 0)

        if config is not None:
            try:
                limit_cfg = int(getattr(config.agents, "context_window", 0))
                if limit_cfg > 0:
                    total_limit = limit_cfg
            except (TypeError, ValueError):
                pass

        if used == 0 and budget is not None:
            # Fallback: count history tokens
            orch = getattr(session, "orchestrator", None)
            if orch:
                history = getattr(orch, "_conversation_history", [])
                used = sum(len(str(m.get("content", ""))) // 4 for m in history)

        pct = min(int(used / total_limit * 100), 100) if total_limit > 0 else 0

        # Build bar (20 chars wide)
        filled = pct * 20 // 100
        bar_full = "█" * filled + "░" * (20 - filled)
        if pct >= 80:
            bar_color = "red"
        elif pct >= 60:
            bar_color = "yellow"
        else:
            bar_color = "green"

        def _fmt(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        lines = [
            f"**Context Window Usage**\n",
            f"`[{bar_full}]` {pct}%",
            f"",
            f"Used:  {_fmt(used)} / {_fmt(total_limit)} tokens",
        ]
        if prompt_tokens or completion_tokens:
            lines.append(f"Prompt:     {_fmt(prompt_tokens)}")
            lines.append(f"Completion: {_fmt(completion_tokens)}")

        orch = getattr(session, "orchestrator", None)
        if orch:
            history = getattr(orch, "_conversation_history", [])
            lines.append(f"Messages:   {len(history)}")

        if pct >= 80:
            lines.append(f"\n⚠️  Context at {pct}% — consider `/compact` to free space.")
        lines.append("\nTip: `/context tree` — show sections with token breakdown")
        return "\n".join(lines)

    registry.register(SlashCommand("context", "Show context window usage gauge", context_handler))

    # Task 278: /mention — inject file into next turn
    # _mentions stored on registry
    registry._mentions: list[str] = []

    async def mention_handler(arg: str = "", **_: Any) -> str:
        """/mention <file> — inject file content into next message context."""
        if not arg.strip():
            if not registry._mentions:
                return "No files mentioned. Usage: `/mention src/foo.py`"
            lines = ["**Mentioned files (injected into next turn):**\n"]
            for f in registry._mentions:
                lines.append(f"  · {f}")
            return "\n".join(lines)

        path_str = arg.strip()
        from pathlib import Path as _Path
        p = _Path(path_str)
        if not p.exists():
            return f"File not found: `{path_str}`"
        if path_str not in registry._mentions:
            registry._mentions.append(path_str)
        return f"File `{path_str}` will be injected into your next message."

    registry.register(SlashCommand("mention", "Inject a file into the next agent turn", mention_handler))

    # Task 279: /model — switch model in-session
    async def model_handler(arg: str = "", **_: Any) -> str:
        """/model [name] — show or switch current model."""
        session = registry._session
        config = getattr(session, "config", None)
        llm = getattr(session, "llm", None)

        if not arg.strip():
            current = getattr(config.llm, "default_model", "?") if config else "?"
            return f"**Current model:** `{current}`\n\nUsage: `/model <name>` — e.g. `/model claude-opus-4-6`"

        new_model = arg.strip()
        if config is not None:
            config.llm.default_model = new_model
        if llm is not None and hasattr(llm, "set_default_model"):
            llm.set_default_model(new_model)
        return f"Model switched to `{new_model}` — takes effect on next request."

    registry.register(SlashCommand("model", "Show or switch the current LLM model", model_handler))

    # Task 280: /theme — color theme
    _THEMES = {
        "dark":       {"bg": "grey7",    "accent": "cyan",   "label": "Dark (default)"},
        "light":      {"bg": "grey93",   "accent": "blue",   "label": "Light"},
        "solarized":  {"bg": "grey19",   "accent": "yellow", "label": "Solarized"},
        "nord":       {"bg": "grey15",   "accent": "steel_blue1", "label": "Nord"},
        "monokai":    {"bg": "grey11",   "accent": "chartreuse1", "label": "Monokai"},
    }
    registry._theme: str = "dark"

    async def theme_handler(arg: str = "", **_: Any) -> str:
        """/theme [name] — show or set the color theme."""
        if not arg.strip():
            lines = ["**Available themes:**\n"]
            for name, cfg in _THEMES.items():
                marker = " ← current" if name == registry._theme else ""
                lines.append(f"  · `{name}` — {cfg['label']}{marker}")
            lines.append("\nUsage: `/theme <name>`")
            return "\n".join(lines)

        name = arg.strip().lower()
        if name not in _THEMES:
            available = ", ".join(f"`{t}`" for t in _THEMES)
            return f"Unknown theme `{name}`. Available: {available}"

        registry._theme = name
        cfg = _THEMES[name]
        return (
            f"Theme set to **{cfg['label']}**. "
            f"Accent: `{cfg['accent']}`, Background hint: `{cfg['bg']}`.\n"
            "_(Full theme support requires terminal restart — accent colors applied immediately.)_"
        )

    registry.register(SlashCommand("theme", "Show or set color theme", theme_handler))

    # Task 281: /add-dir — extend file access scope
    registry._extra_dirs: list[str] = []

    async def adddir_handler(arg: str = "", **_: Any) -> str:
        """/add-dir [path] — add an external directory to the session scope."""
        if not arg.strip():
            if not registry._extra_dirs:
                return "No extra directories added. Usage: `/add-dir ../backend`"
            lines = ["**Extra directories in scope:**\n"]
            for d in registry._extra_dirs:
                lines.append(f"  · {d}")
            return "\n".join(lines)

        from pathlib import Path as _Path
        path_str = arg.strip()
        p = _Path(path_str).resolve()
        if not p.exists():
            return f"Directory not found: `{path_str}`"
        if not p.is_dir():
            return f"`{path_str}` is not a directory."
        resolved = str(p)
        if resolved not in registry._extra_dirs:
            registry._extra_dirs.append(resolved)
            return f"Added `{resolved}` to session scope."
        return f"`{resolved}` is already in scope."

    registry.register(SlashCommand("add-dir", "Add an external directory to session scope", adddir_handler))

    # Task 283: /checkpoint — manage file checkpoints
    registry._checkpoint_mgr: Any = None  # set by app.py after wiring

    async def checkpoint_handler(arg: str = "", **_: Any) -> str:
        """/checkpoint [list|undo N] — manage pre-write checkpoints."""
        from lidco.cli.checkpoint import CheckpointManager
        mgr = registry._checkpoint_mgr
        if mgr is None:
            return "Checkpoint manager not initialized."

        parts = arg.strip().split()
        sub = parts[0].lower() if parts else "list"

        if sub == "list":
            count = mgr.count()
            if count == 0:
                return "No checkpoints stored."
            recent = mgr.peek(5)
            lines = [f"**Checkpoints: {count} stored (last 5):**\n"]
            for i, cp in enumerate(recent, 1):
                existed = "modified" if cp.existed else "created"
                lines.append(f"  {i}. `{cp.path}` ({existed})")
            return "\n".join(lines)

        if sub == "undo":
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            restored = mgr.restore(n)
            if not restored:
                return "Nothing to undo."
            return f"Restored {len(restored)} file(s): " + ", ".join(f"`{p}`" for p in restored)

        if sub == "clear":
            mgr.clear()
            return "All checkpoints cleared."

        return (
            "**Usage:** `/checkpoint [list|undo [N]|clear]`\n\n"
            "- `/checkpoint` or `/checkpoint list` — show stored checkpoints\n"
            "- `/checkpoint undo [N]` — restore last N file writes (default: 1)\n"
            "- `/checkpoint clear` — discard all checkpoints"
        )

    registry.register(SlashCommand("checkpoint", "Manage pre-write file checkpoints", checkpoint_handler))

    # Task 285: /session — save/load/list sessions
    registry._session_store: Any = None  # set lazily

    async def session_handler(arg: str = "", **_: Any) -> str:
        """/session [save [id]|list [--query Q] [--since Nd]|load <id>|delete <id>|rename <n>] — manage sessions."""
        from lidco.cli.session_store import SessionStore
        if registry._session_store is None:
            registry._session_store = SessionStore()
        store: "SessionStore" = registry._session_store

        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            # Task 384: /session list [--query <text>] [--since <Nd>]
            query = ""
            since_days: "int | None" = None
            rest_parts = rest.split()
            i = 0
            while i < len(rest_parts):
                tok = rest_parts[i]
                if tok == "--query" and i + 1 < len(rest_parts):
                    query = rest_parts[i + 1]
                    i += 2
                elif tok == "--since" and i + 1 < len(rest_parts):
                    raw = rest_parts[i + 1]
                    try:
                        since_days = int(raw.rstrip("d"))
                    except ValueError:
                        return f"Invalid --since value: `{raw}`. Use e.g. `7d` or `7`."
                    i += 2
                else:
                    i += 1

            if query or since_days is not None:
                results = store.search(query=query, since_days=since_days)
                if not results:
                    return "No sessions found matching your criteria."
                try:
                    from rich.table import Table as _Table
                    from rich.console import Console as _Con
                    import io as _io
                    t = _Table(show_header=True, header_style="bold cyan")
                    t.add_column("ID", style="dim", no_wrap=True)
                    t.add_column("Date")
                    t.add_column("Msgs", justify="right")
                    t.add_column("Preview")
                    for s in results:
                        ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                        t.add_row(s["session_id"], ts, str(s["message_count"]), s["first_user_message"][:60])
                    buf = _io.StringIO()
                    c = _Con(file=buf, highlight=False)
                    c.print(t)
                    return buf.getvalue().rstrip()
                except Exception:
                    lines = ["**Sessions matching criteria:**\n"]
                    for s in results:
                        ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                        lines.append(f"  · `{s['session_id']}` — {ts} · {s['first_user_message'][:60]}")
                    return "\n".join(lines)

            sessions = store.list_sessions()
            if not sessions:
                return "No saved sessions. Use `/session save` to save the current session."
            lines = ["**Saved sessions:**\n"]
            for s in sessions:
                ts = s["saved_at"][:19].replace("T", " ") if s["saved_at"] else "?"
                name_tag = f" ({s['metadata'].get('name')})" if s.get("metadata", {}).get("name") else ""
                lines.append(f"  · `{s['session_id']}`{name_tag} — {ts} ({s['message_count']} messages)")
            return "\n".join(lines)

        if sub == "save":
            session = registry._session
            orch = getattr(session, "orchestrator", None)
            history = getattr(orch, "_conversation_history", []) if orch else []
            sid = store.save(history, session_id=rest or None)
            return f"Session saved as `{sid}` ({len(history)} messages)."

        if sub == "load":
            if not rest:
                return "Usage: `/session load <session-id>`"
            data = store.load(rest)
            if data is None:
                return f"Session `{rest}` not found."
            session = registry._session
            orch = getattr(session, "orchestrator", None)
            if orch is None:
                return "No active orchestrator to load into."
            orch._conversation_history = data.get("history", [])
            count = len(orch._conversation_history)
            return f"Session `{rest}` loaded — {count} messages restored."

        if sub == "delete":
            if not rest:
                return "Usage: `/session delete <session-id>`"
            if store.delete(rest):
                return f"Session `{rest}` deleted."
            return f"Session `{rest}` not found."

        # Task 383: /session rename <new-name>
        if sub == "rename":
            if not rest:
                return "Usage: `/session rename <new-name>`"
            session = registry._session
            orch = getattr(session, "orchestrator", None)
            history = getattr(orch, "_conversation_history", []) if orch else []
            # Save/update with new name metadata
            current_id = getattr(registry, "_current_session_id", None)
            meta: dict[str, Any] = {"name": rest}
            sid = store.save(history, session_id=current_id, metadata=meta)
            registry._current_session_id = sid
            return f"Session renamed to `{rest}` (saved as `{sid}`)."

        return (
            "**Usage:** `/session [save [id]|list [--query Q] [--since Nd]|load <id>|delete <id>|rename <n>]`\n\n"
            "- `/session save [id]` — save current conversation\n"
            "- `/session list` — list saved sessions\n"
            "- `/session list --query auth` — search sessions by content\n"
            "- `/session list --since 7d` — sessions from last 7 days\n"
            "- `/session load <id>` — restore a saved session\n"
            "- `/session delete <id>` — delete a saved session\n"
            "- `/session rename <name>` — rename current session"
        )

    registry.register(SlashCommand("session", "Save, load, and manage conversation sessions", session_handler))

    # ── Q57 Task 382: /fork — session forking ────────────────────────────
    registry._current_session_id: "str | None" = None
    registry._fork_parent_id: "str | None" = None

    async def fork_handler(arg: str = "", **_: Any) -> str:
        """/fork [name] | back — fork current session or return to parent."""
        from lidco.cli.session_store import SessionStore
        if registry._session_store is None:
            registry._session_store = SessionStore()
        store: "SessionStore" = registry._session_store

        session = registry._session
        orch = getattr(session, "orchestrator", None)
        history = getattr(orch, "_conversation_history", []) if orch else []

        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else parts[0].strip() if parts else ""

        if sub == "back":
            parent_id = registry._fork_parent_id
            if not parent_id:
                return "No parent session to return to."
            data = store.load(parent_id)
            if data is None:
                return f"Parent session `{parent_id}` no longer exists."
            if orch is not None:
                orch._conversation_history = data.get("history", [])
            registry._current_session_id = parent_id
            registry._fork_parent_id = None
            return f"Returned to parent session `{parent_id}` ({len(data.get('history', []))} messages)."

        # Save current history as parent
        fork_name = arg.strip() or None
        parent_id = store.save(history, session_id=registry._current_session_id)
        registry._current_session_id = parent_id

        fork_id = store.fork(parent_id, fork_name=fork_name)
        if fork_id is None:
            return "Failed to create fork."

        # Load fork into current conversation
        fork_data = store.load(fork_id)
        if fork_data and orch is not None:
            orch._conversation_history = fork_data.get("history", [])

        registry._fork_parent_id = parent_id
        registry._current_session_id = fork_id
        name_str = f" (named `{fork_name}`)" if fork_name else ""
        return (
            f"Forked from `{parent_id}` → new fork `{fork_id}`{name_str}.\n"
            f"Use `/fork back` to return to the parent session."
        )

    registry.register(SlashCommand("fork", "Fork current session into a branch", fork_handler))

    # ── Q57 Task 385: /profile — workspace profiles ───────────────────────
    registry._active_profile: "str | None" = None

    async def profile_handler(arg: str = "", **_: Any) -> str:
        """/profile [list|use <name>|save <name>|delete <name>] — manage workspace profiles."""
        from lidco.core.profiles import ProfileLoader
        loader = ProfileLoader()
        project_dir = None
        try:
            from pathlib import Path as _Path
            project_dir = _Path.cwd()
        except Exception:
            pass

        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list" or not arg.strip():
            names = loader.list_profiles(project_dir)
            if not names:
                return "No profiles available."
            lines = ["**Available profiles:**\n"]
            for n in names:
                marker = " ← active" if n == registry._active_profile else ""
                desc = loader.load(n, project_dir)
                desc_str = desc.get("description", "") if desc else ""
                lines.append(f"  · `{n}`{marker}" + (f" — {desc_str}" if desc_str else ""))
            lines.append("\nUsage: `/profile use <name>`")
            return "\n".join(lines)

        if sub == "use":
            if not rest:
                return "Usage: `/profile use <name>`"
            data = loader.load(rest, project_dir)
            if data is None:
                return f"Profile `{rest}` not found. Use `/profile list` to see available profiles."
            # Apply agent/llm settings
            session = registry._session
            config = getattr(session, "config", None)
            if config is not None:
                if "agents" in data and isinstance(data["agents"], dict):
                    for k, v in data["agents"].items():
                        if hasattr(config.agents, k):
                            try:
                                setattr(config.agents, k, v)
                            except Exception:
                                pass
                if "llm" in data and isinstance(data["llm"], dict):
                    for k, v in data["llm"].items():
                        if hasattr(config.llm, k):
                            try:
                                setattr(config.llm, k, v)
                            except Exception:
                                pass
            registry._active_profile = rest
            desc_str = data.get("description", rest)
            return f"Profile `{rest}` activated ({desc_str})."

        if sub == "save":
            if not rest:
                return "Usage: `/profile save <name>`"
            session = registry._session
            config = getattr(session, "config", None)
            data: "dict[str, Any]" = {"name": rest}
            if config is not None:
                data["agents"] = {
                    "default": config.agents.default,
                    "auto_review": config.agents.auto_review,
                    "auto_plan": config.agents.auto_plan,
                }
                data["llm"] = {
                    "default_model": config.llm.default_model,
                    "temperature": config.llm.temperature,
                }
            try:
                path = loader.save(rest, data, project_dir)
                return f"Profile `{rest}` saved to `{path}`."
            except Exception as exc:
                return f"Failed to save profile: {exc}"

        if sub == "delete":
            if not rest:
                return "Usage: `/profile delete <name>`"
            if loader.delete(rest, project_dir):
                if registry._active_profile == rest:
                    registry._active_profile = None
                return f"Profile `{rest}` deleted."
            return f"Profile `{rest}` not found (built-ins cannot be deleted)."

        return (
            "**Usage:** `/profile [list|use <name>|save <name>|delete <name>]`\n\n"
            "- `/profile list` — show available profiles\n"
            "- `/profile use frontend` — activate a profile\n"
            "- `/profile save myprofile` — save current settings as profile\n"
            "- `/profile delete myprofile` — remove a saved profile"
        )

    registry.register(SlashCommand("workprofile", "Manage workspace configuration profiles", profile_handler))

    # ── Q57 Task 386: /replay — session replay ────────────────────────────

    async def replay_handler(arg: str = "", **_: Any) -> str:
        """/replay [session-id] [--dry-run] — replay user messages from a saved session."""
        from lidco.cli.session_store import SessionStore
        if registry._session_store is None:
            registry._session_store = SessionStore()
        store: "SessionStore" = registry._session_store

        parts = arg.strip().split()
        dry_run = "--dry-run" in parts
        session_id_parts = [p for p in parts if not p.startswith("--")]
        session_id = session_id_parts[0] if session_id_parts else None

        if not session_id:
            return (
                "**Usage:** `/replay <session-id> [--dry-run]`\n\n"
                "- `/replay abc123` — replay messages from session\n"
                "- `/replay abc123 --dry-run` — preview without sending"
            )

        data = store.load(session_id)
        if data is None:
            return f"Session `{session_id}` not found."

        history = data.get("history", [])
        user_messages = [
            m.get("content", "") for m in history if m.get("role") == "user"
        ]
        if not user_messages:
            return f"Session `{session_id}` has no user messages to replay."

        if dry_run:
            lines = [f"**Dry run — {len(user_messages)} messages from `{session_id}`:**\n"]
            for i, msg in enumerate(user_messages, 1):
                preview = str(msg)[:100].replace("\n", " ")
                lines.append(f"  {i}. {preview}")
            return "\n".join(lines)

        # Confirm with user (non-blocking best effort)
        lines = [f"**Replaying {len(user_messages)} message(s) from `{session_id}`...**\n"]
        session = registry._session
        orch = getattr(session, "orchestrator", None)
        if orch is None:
            return "No active orchestrator to replay into."

        for i, msg in enumerate(user_messages, 1):
            preview = str(msg)[:60].replace("\n", " ")
            lines.append(f"  [{i}/{len(user_messages)}] Sending: {preview}…")
            try:
                await orch.handle(str(msg))
            except Exception as exc:
                lines.append(f"  ⚠ Error on message {i}: {exc}")
                break

        lines.append("\nReplay complete.")
        return "\n".join(lines)

    registry.register(SlashCommand("replay", "Replay user messages from a saved session", replay_handler))

    # ── Q57 Task 388: /repos — multi-repo support ─────────────────────────
    registry._extra_repos: "list[str]" = []

    async def repos_handler(arg: str = "", **_: Any) -> str:
        """/repos [add <path>|remove <path>|list] — manage additional repos."""
        import subprocess as _subprocess
        from pathlib import Path as _Path

        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list" or not arg.strip():
            if not registry._extra_repos:
                return (
                    "No extra repositories configured.\n"
                    "Usage: `/repos add <path>`"
                )
            lines = ["**Extra repositories:**\n"]
            for repo in registry._extra_repos:
                lines.append(f"  · `{repo}`")
            lines.append("\nOn each turn, git status + branch for these repos will be injected into context.")
            return "\n".join(lines)

        if sub == "add":
            if not rest:
                return "Usage: `/repos add <path>`"
            p = _Path(rest).resolve()
            if not p.exists():
                return f"Path not found: `{rest}`"
            if not p.is_dir():
                return f"`{rest}` is not a directory."
            resolved = str(p)
            if resolved in registry._extra_repos:
                return f"`{resolved}` is already in the repos list."
            # Verify it's a git repo
            try:
                r = _subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    cwd=resolved,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode != 0:
                    return f"`{resolved}` does not appear to be a git repository."
            except Exception:
                pass  # If git check fails, still add it
            registry._extra_repos.append(resolved)
            return f"Added `{resolved}` to repos list."

        if sub == "remove":
            if not rest:
                return "Usage: `/repos remove <path>`"
            p = _Path(rest).resolve()
            resolved = str(p)
            if resolved in registry._extra_repos:
                registry._extra_repos.remove(resolved)
                return f"Removed `{resolved}` from repos list."
            # Try fuzzy match
            if rest in registry._extra_repos:
                registry._extra_repos.remove(rest)
                return f"Removed `{rest}` from repos list."
            return f"`{rest}` not found in repos list."

        return (
            "**Usage:** `/repos [add <path>|remove <path>|list]`\n\n"
            "- `/repos add ../backend` — add a repo\n"
            "- `/repos remove ../backend` — remove a repo\n"
            "- `/repos list` — show configured repos"
        )

    registry.register(SlashCommand("repos", "Manage multiple repositories", repos_handler))
