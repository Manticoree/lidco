"""
Q273 CLI commands — /widgets, /file-picker, /diff-view, /progress-view

Registered via register_q273_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q273_commands(registry) -> None:
    """Register Q273 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /widgets — Widget manager
    # ------------------------------------------------------------------
    async def widgets_handler(args: str) -> str:
        """
        Usage: /widgets list
               /widgets focus <id>
               /widgets hide <id>
               /widgets show <id>
        """
        from lidco.widgets.framework import WidgetManager

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /widgets <subcommand>\n"
                "  list           list all widgets\n"
                "  focus <id>     focus a widget\n"
                "  hide <id>      hide a widget\n"
                "  show <id>      show a widget"
            )

        subcmd = parts[0].lower()
        # Use a singleton-ish manager stored on the function
        if not hasattr(widgets_handler, "_mgr"):
            widgets_handler._mgr = WidgetManager()
        mgr = widgets_handler._mgr

        if subcmd == "list":
            widgets = mgr.all_widgets()
            if not widgets:
                return "No widgets registered."
            lines = []
            for w in widgets:
                state = "visible" if w.is_visible() else "hidden"
                focus = " [focused]" if w.is_focused() else ""
                lines.append(f"  {w.id}: {w.title} ({state}){focus}")
            return "Widgets:\n" + "\n".join(lines)

        if subcmd == "focus":
            if len(parts) < 2:
                return "Error: widget id required."
            w = mgr.get(parts[1])
            if w is None:
                return f"Error: widget '{parts[1]}' not found."
            # Blur current
            current = mgr.focused()
            if current:
                current.blur()
            w.focus()
            return f"Focused: {w.id}"

        if subcmd == "hide":
            if len(parts) < 2:
                return "Error: widget id required."
            w = mgr.get(parts[1])
            if w is None:
                return f"Error: widget '{parts[1]}' not found."
            w.hide()
            return f"Hidden: {w.id}"

        if subcmd == "show":
            if len(parts) < 2:
                return "Error: widget id required."
            w = mgr.get(parts[1])
            if w is None:
                return f"Error: widget '{parts[1]}' not found."
            w.show()
            return f"Shown: {w.id}"

        return f"Unknown subcommand: {subcmd}"

    registry.register_async("widgets", "Manage interactive widgets", widgets_handler)

    # ------------------------------------------------------------------
    # /file-picker — File picker widget
    # ------------------------------------------------------------------
    async def file_picker_handler(args: str) -> str:
        """
        Usage: /file-picker search <query>
               /file-picker bookmark <path>
               /file-picker recent
        """
        from lidco.widgets.file_picker import FilePicker

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /file-picker <subcommand>\n"
                "  search <query>    fuzzy search files\n"
                "  bookmark <path>   add bookmark\n"
                "  recent            show recent files"
            )

        if not hasattr(file_picker_handler, "_picker"):
            file_picker_handler._picker = FilePicker()
        picker = file_picker_handler._picker

        subcmd = parts[0].lower()

        if subcmd == "search":
            query = parts[1] if len(parts) > 1 else ""
            results = picker.search(query)
            if not results:
                return "No files found."
            lines = [f"  {e.path} ({'dir' if e.is_dir else f'{e.size}B'})" for e in results]
            return f"Found {len(results)} files:\n" + "\n".join(lines)

        if subcmd == "bookmark":
            if len(parts) < 2:
                return "Error: path required."
            picker.add_bookmark(parts[1])
            return f"Bookmarked: {parts[1]}"

        if subcmd == "recent":
            items = picker.recent()
            if not items:
                return "No recent files."
            return "Recent:\n" + "\n".join(f"  {p}" for p in items)

        return f"Unknown subcommand: {subcmd}"

    registry.register_async("file-picker", "Interactive file selection widget", file_picker_handler)

    # ------------------------------------------------------------------
    # /diff-view — Diff viewer widget
    # ------------------------------------------------------------------
    async def diff_view_handler(args: str) -> str:
        """
        Usage: /diff-view set <old> <new>
               /diff-view hunks
               /diff-view accept <id>
               /diff-view reject <id>
               /diff-view apply
        """
        from lidco.widgets.diff_viewer import DiffViewer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /diff-view <subcommand>\n"
                "  set <old> <new>   set old and new content\n"
                "  hunks             list hunks\n"
                "  accept <id>       accept a hunk\n"
                "  reject <id>       reject a hunk\n"
                "  apply             apply accepted hunks"
            )

        if not hasattr(diff_view_handler, "_viewer"):
            diff_view_handler._viewer = DiffViewer()
        viewer = diff_view_handler._viewer

        subcmd = parts[0].lower()

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: old and new content required."
            viewer.set_contents(parts[1], parts[2])
            s = viewer.stats()
            return f"Diff computed: {s['total']} hunks."

        if subcmd == "hunks":
            hunks = viewer.hunks()
            if not hunks:
                return "No hunks."
            lines = []
            for h in hunks:
                lines.append(f"  #{h.id} [{h.status}] old@{h.old_start} new@{h.new_start}")
            return "Hunks:\n" + "\n".join(lines)

        if subcmd == "accept":
            if len(parts) < 2:
                return "Error: hunk id required."
            ok = viewer.accept_hunk(int(parts[1]))
            return f"Hunk #{parts[1]} accepted." if ok else f"Hunk #{parts[1]} not found."

        if subcmd == "reject":
            if len(parts) < 2:
                return "Error: hunk id required."
            ok = viewer.reject_hunk(int(parts[1]))
            return f"Hunk #{parts[1]} rejected." if ok else f"Hunk #{parts[1]} not found."

        if subcmd == "apply":
            result = viewer.apply()
            return f"Applied. Result:\n{result}"

        return f"Unknown subcommand: {subcmd}"

    registry.register_async("diff-view", "Side-by-side diff viewer with hunk management", diff_view_handler)

    # ------------------------------------------------------------------
    # /progress-view — Progress dashboard widget
    # ------------------------------------------------------------------
    async def progress_view_handler(args: str) -> str:
        """
        Usage: /progress-view add <name>
               /progress-view update <id> <progress>
               /progress-view complete <id>
               /progress-view status
        """
        from lidco.widgets.progress_dashboard import ProgressDashboard

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /progress-view <subcommand>\n"
                "  add <name>              add a task\n"
                "  update <id> <progress>  update progress (0-100)\n"
                "  complete <id>           mark task complete\n"
                "  status                  show summary"
            )

        if not hasattr(progress_view_handler, "_dash"):
            progress_view_handler._dash = ProgressDashboard()
        dash = progress_view_handler._dash

        subcmd = parts[0].lower()

        if subcmd == "add":
            if len(parts) < 2:
                return "Error: task name required."
            name = " ".join(parts[1:])
            task = dash.add_task(name)
            return f"Task added: {task.id} ({task.name})"

        if subcmd == "update":
            if len(parts) < 3:
                return "Error: task id and progress required."
            task = dash.update_task(parts[1], float(parts[2]))
            if task is None:
                return f"Error: task '{parts[1]}' not found."
            return f"Updated: {task.id} -> {task.progress:.0f}% [{task.status}]"

        if subcmd == "complete":
            if len(parts) < 2:
                return "Error: task id required."
            task = dash.complete_task(parts[1])
            if task is None:
                return f"Error: task '{parts[1]}' not found."
            return f"Completed: {task.id}"

        if subcmd == "status":
            s = dash.summary()
            return json.dumps(s, indent=2)

        return f"Unknown subcommand: {subcmd}"

    registry.register_async("progress-view", "Multi-task progress dashboard", progress_view_handler)
