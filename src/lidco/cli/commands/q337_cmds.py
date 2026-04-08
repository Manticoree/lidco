"""Q337 CLI commands — /timer, /focus, /standup, /retro

Registered via register_q337_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q337_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q337 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /timer — Time tracking
    # ------------------------------------------------------------------
    async def timer_handler(args: str) -> str:
        """
        Usage: /timer start <task> [--project <name>] [--tags <t1,t2>]
               /timer stop
               /timer status
               /timer report [--days <n>]
               /timer git [--limit <n>]
               /timer export
        """
        from lidco.productivity.timer import TimeTracker

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /timer <subcommand>\n"
                "  start <task> [--project <p>] [--tags <t1,t2>]  start tracking\n"
                "  stop                                            stop tracking\n"
                "  status                                          show active task\n"
                "  report [--days <n>]                             time report\n"
                "  git [--limit <n>]                               detect from git\n"
                "  export                                          export as JSON"
            )

        subcmd = parts[0].lower()
        tracker = TimeTracker()

        if subcmd == "start":
            if len(parts) < 2:
                return "Usage: /timer start <task> [--project <name>] [--tags <t1,t2>]"
            task = parts[1]
            project = "default"
            tags = []
            i = 2
            while i < len(parts):
                if parts[i] == "--project" and i + 1 < len(parts):
                    project = parts[i + 1]
                    i += 2
                elif parts[i] == "--tags" and i + 1 < len(parts):
                    tags = [t.strip() for t in parts[i + 1].split(",")]
                    i += 2
                else:
                    i += 1
            entry = tracker.start(task, project=project, tags=tags)
            return (
                f"Started tracking: {entry.task}\n"
                f"Project: {entry.project}\n"
                f"Tags: {', '.join(entry.tags) if entry.tags else '(none)'}"
            )

        if subcmd == "stop":
            entry = tracker.stop()
            if entry is None:
                return "No active task to stop."
            secs = entry.duration().total_seconds()
            mins = int(secs // 60)
            return f"Stopped: {entry.task} ({mins}m)"

        if subcmd == "status":
            active = tracker.active
            if active is None:
                return "No active task."
            secs = active.duration().total_seconds()
            mins = int(secs // 60)
            return f"Active: {active.task} (project: {active.project}, {mins}m elapsed)"

        if subcmd == "report":
            report = tracker.report()
            return report.summary()

        if subcmd == "git":
            limit = 20
            i = 1
            while i < len(parts):
                if parts[i] == "--limit" and i + 1 < len(parts):
                    try:
                        limit = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                else:
                    i += 1
            entries = tracker.detect_from_git(limit=limit)
            if not entries:
                return "No git commits found."
            lines = [f"Detected {len(entries)} entries from git:"]
            for e in entries[:10]:
                lines.append(f"  [{e.start.date()}] {e.task}")
            if len(entries) > 10:
                lines.append(f"  ... and {len(entries) - 10} more")
            return "\n".join(lines)

        if subcmd == "export":
            return tracker.export_json()

        return f"Unknown subcommand '{subcmd}'. Use start/stop/status/report/git/export."

    registry.register_async("timer", "Track time per task", timer_handler)

    # ------------------------------------------------------------------
    # /focus — Focus mode with Pomodoro
    # ------------------------------------------------------------------
    async def focus_handler(args: str) -> str:
        """
        Usage: /focus start [--work <min>] [--break <min>]
               /focus stop
               /focus pause / resume
               /focus cycle
               /focus status
               /focus stats
        """
        from lidco.productivity.focus import FocusConfig, FocusMode

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /focus <subcommand>\n"
                "  start [--work <min>] [--break <min>]  start focus mode\n"
                "  stop                                  stop focus mode\n"
                "  pause                                 pause session\n"
                "  resume                                resume session\n"
                "  cycle                                 complete Pomodoro cycle\n"
                "  status                                show current status\n"
                "  stats                                 show statistics"
            )

        subcmd = parts[0].lower()
        fm = FocusMode()

        if subcmd == "start":
            work = 25
            brk = 5
            i = 1
            while i < len(parts):
                if parts[i] == "--work" and i + 1 < len(parts):
                    try:
                        work = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                elif parts[i] == "--break" and i + 1 < len(parts):
                    try:
                        brk = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                else:
                    i += 1
            config = FocusConfig(work_minutes=work, short_break_minutes=brk)
            session = fm.start(config)
            return (
                f"Focus mode started ({session.session_id})\n"
                f"Work: {work}m, Break: {brk}m\n"
                f"Notifications blocked: {config.block_notifications}"
            )

        if subcmd == "stop":
            session = fm.stop()
            if session is None:
                return "No active focus session."
            mins = int(session.total_focus_seconds / 60)
            return (
                f"Focus session ended.\n"
                f"Cycles completed: {session.completed_cycles}\n"
                f"Total focus time: {mins}m"
            )

        if subcmd == "pause":
            ok = fm.pause()
            return "Session paused." if ok else "No active session to pause."

        if subcmd == "resume":
            ok = fm.resume()
            return "Session resumed." if ok else "No paused session to resume."

        if subcmd == "cycle":
            phase = fm.complete_cycle()
            return f"Cycle complete. Now: {phase.value}"

        if subcmd == "status":
            state = fm.state
            return f"Focus state: {state.value}, Phase: {fm.phase.value}"

        if subcmd == "stats":
            s = fm.stats()
            return (
                f"Focus stats:\n"
                f"  Sessions: {s.total_sessions}\n"
                f"  Total focus: {int(s.total_focus_seconds / 60)}m\n"
                f"  Cycles: {s.total_cycles}\n"
                f"  Avg session: {s.avg_session_minutes:.1f}m"
            )

        return f"Unknown subcommand '{subcmd}'. Use start/stop/pause/resume/cycle/status/stats."

    registry.register_async("focus", "Focus mode with Pomodoro timer", focus_handler)

    # ------------------------------------------------------------------
    # /standup — Daily standup notes
    # ------------------------------------------------------------------
    async def standup_handler(args: str) -> str:
        """
        Usage: /standup
               /standup plan <item>
               /standup blocker <item>
               /standup generate [--author <name>]
               /standup slack [--author <name>]
               /standup clear
        """
        from lidco.productivity.standup import StandupGenerator

        parts = shlex.split(args) if args.strip() else []
        gen = StandupGenerator()

        if not parts or parts[0].lower() == "generate":
            author = None
            i = 1
            while i < len(parts):
                if parts[i] == "--author" and i + 1 < len(parts):
                    author = parts[i + 1]
                    i += 2
                else:
                    i += 1
            note = gen.generate(author=author)
            return note.format()

        subcmd = parts[0].lower()

        if subcmd == "plan":
            if len(parts) < 2:
                return "Usage: /standup plan <item>"
            item = " ".join(parts[1:])
            gen.add_plan(item)
            return f"Added plan: {item}"

        if subcmd == "blocker":
            if len(parts) < 2:
                return "Usage: /standup blocker <item>"
            item = " ".join(parts[1:])
            gen.add_blocker(item)
            return f"Added blocker: {item}"

        if subcmd == "slack":
            author = None
            i = 1
            while i < len(parts):
                if parts[i] == "--author" and i + 1 < len(parts):
                    author = parts[i + 1]
                    i += 2
                else:
                    i += 1
            note = gen.generate(author=author)
            return gen.format_slack(note)

        if subcmd == "clear":
            gen.clear()
            return "Cleared plans and blockers."

        return f"Unknown subcommand '{subcmd}'. Use plan/blocker/generate/slack/clear."

    registry.register_async("standup", "Generate daily standup notes", standup_handler)

    # ------------------------------------------------------------------
    # /retro — Retrospective generation
    # ------------------------------------------------------------------
    async def retro_handler(args: str) -> str:
        """
        Usage: /retro
               /retro well <text>
               /retro improve <text>
               /retro action <text> [--assignee <name>]
               /retro generate [--title <title>]
               /retro clear
        """
        from lidco.productivity.retro import RetroGenerator

        parts = shlex.split(args) if args.strip() else []
        gen = RetroGenerator()

        if not parts or parts[0].lower() == "generate":
            title = "Sprint Retrospective"
            i = 1
            while i < len(parts):
                if parts[i] == "--title" and i + 1 < len(parts):
                    title = parts[i + 1]
                    i += 2
                else:
                    i += 1
            retro = gen.generate(title=title)
            return retro.format()

        subcmd = parts[0].lower()

        if subcmd == "well":
            if len(parts) < 2:
                return "Usage: /retro well <text>"
            text = " ".join(parts[1:])
            gen.add_item("well", text)
            return f"Added: + {text}"

        if subcmd == "improve":
            if len(parts) < 2:
                return "Usage: /retro improve <text>"
            text = " ".join(parts[1:])
            gen.add_item("improve", text)
            return f"Added: - {text}"

        if subcmd == "action":
            if len(parts) < 2:
                return "Usage: /retro action <text> [--assignee <name>]"
            assignee = ""
            text_parts = []
            i = 1
            while i < len(parts):
                if parts[i] == "--assignee" and i + 1 < len(parts):
                    assignee = parts[i + 1]
                    i += 2
                else:
                    text_parts.append(parts[i])
                    i += 1
            text = " ".join(text_parts)
            gen.add_action(text, assignee=assignee)
            assignee_str = f" (assigned to {assignee})" if assignee else ""
            return f"Action added: {text}{assignee_str}"

        if subcmd == "clear":
            gen.clear()
            return "Cleared retrospective data."

        return f"Unknown subcommand '{subcmd}'. Use well/improve/action/generate/clear."

    registry.register_async("retro", "Generate retrospective from session data", retro_handler)
