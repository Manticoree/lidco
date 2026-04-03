"""Q271 CLI commands: /shortcuts, /shortcut-profile, /palette, /shortcut-train."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q271 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # lazy singletons
    def _reg():
        from lidco.shortcuts.registry import ShortcutRegistry
        if "registry" not in _state:
            _state["registry"] = ShortcutRegistry()
        return _state["registry"]

    def _profiles():
        from lidco.shortcuts.profiles import ShortcutProfiles
        if "profiles" not in _state:
            _state["profiles"] = ShortcutProfiles(_reg())
        return _state["profiles"]

    def _palette():
        from lidco.shortcuts.palette import CommandPalette
        if "palette" not in _state:
            _state["palette"] = CommandPalette()
        return _state["palette"]

    def _trainer():
        from lidco.shortcuts.trainer import ShortcutTrainer
        if "trainer" not in _state:
            _state["trainer"] = ShortcutTrainer(_reg())
        return _state["trainer"]

    # ------------------------------------------------------------------ #
    # /shortcuts                                                          #
    # ------------------------------------------------------------------ #

    async def shortcuts_handler(args: str) -> str:
        from lidco.shortcuts.registry import Shortcut
        import json

        reg = _reg()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else "list"

        if sub == "list":
            shortcuts = reg.all_shortcuts()
            if not shortcuts:
                return "No shortcuts registered."
            lines = ["Shortcuts:"]
            for s in shortcuts:
                status = "on" if s.enabled else "off"
                lines.append(f"  {s.keys}  -> {s.command}  [{s.context}] ({status})")
            return "\n".join(lines)

        if sub == "add":
            # re-split from original args: "add <keys> <command>"
            rest = args.strip().split(maxsplit=1)
            if len(rest) < 2:
                return "Usage: /shortcuts add <keys> <command>"
            after_sub = rest[1].strip().split(maxsplit=1)
            if len(after_sub) < 2:
                return "Usage: /shortcuts add <keys> <command>"
            keys, command = after_sub
            try:
                s = reg.register(Shortcut(keys=keys, command=command))
                return f"Registered: {s.keys} -> {s.command}"
            except ValueError as exc:
                return str(exc)

        if sub == "remove":
            keys = parts[1] if len(parts) > 1 else ""
            if not keys:
                return "Usage: /shortcuts remove <keys>"
            if reg.unregister(keys.strip()):
                return f"Removed shortcut '{keys.strip()}'."
            return f"Shortcut '{keys.strip()}' not found."

        if sub == "find":
            command = parts[1] if len(parts) > 1 else ""
            if not command:
                return "Usage: /shortcuts find <command>"
            found = reg.find_by_command(command.strip())
            if not found:
                return f"No shortcuts for command '{command.strip()}'."
            lines = [f"Shortcuts for '{command.strip()}':"]
            for s in found:
                lines.append(f"  {s.keys}  [{s.context}]")
            return "\n".join(lines)

        if sub == "summary":
            return json.dumps(reg.summary(), indent=2)

        return "Usage: /shortcuts [list | add <keys> <command> | remove <keys> | find <command>]"

    registry.register(SlashCommand("shortcuts", "Manage keyboard shortcuts", shortcuts_handler))

    # ------------------------------------------------------------------ #
    # /shortcut-profile                                                   #
    # ------------------------------------------------------------------ #

    async def profile_handler(args: str) -> str:
        import json

        profiles = _profiles()
        parts = args.strip().split(maxsplit=3)
        sub = parts[0].lower() if parts else "list"

        if sub == "list":
            all_p = profiles.all_profiles()
            active = profiles.active()
            lines = ["Profiles:"]
            for p in all_p:
                marker = " *" if p.name == active else ""
                lines.append(f"  {p.name}{marker}  ({len(p.shortcuts)} shortcuts)")
            return "\n".join(lines)

        if sub == "activate":
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                return "Usage: /shortcut-profile activate <name>"
            if profiles.activate(name):
                return f"Activated profile '{name}'."
            return f"Profile '{name}' not found."

        if sub == "create":
            name = parts[1] if len(parts) > 1 else ""
            if not name:
                return "Usage: /shortcut-profile create <name>"
            profiles.create(name)
            return f"Created profile '{name}'."

        if sub == "merge":
            if len(parts) < 4:
                return "Usage: /shortcut-profile merge <base> <overlay> <new>"
            try:
                merged = profiles.merge(parts[1], parts[2], parts[3])
                return f"Merged profile '{merged.name}' ({len(merged.shortcuts)} shortcuts)."
            except ValueError as exc:
                return str(exc)

        if sub == "summary":
            return json.dumps(profiles.summary(), indent=2)

        return "Usage: /shortcut-profile [list | activate <name> | create <name> | merge <base> <overlay> <new>]"

    registry.register(SlashCommand("shortcut-profile", "Manage shortcut profiles", profile_handler))

    # ------------------------------------------------------------------ #
    # /palette                                                             #
    # ------------------------------------------------------------------ #

    async def palette_handler(args: str) -> str:
        import json

        pal = _palette()
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else "recent"

        if sub == "search":
            query = parts[1] if len(parts) > 1 else ""
            if not query:
                return "Usage: /palette search <query>"
            results = pal.search(query)
            if not results:
                return "No matches."
            lines = ["Results:"]
            for e in results:
                lines.append(f"  {e.command}  — {e.description}  (score={e.score})")
            return "\n".join(lines)

        if sub == "recent":
            items = pal.recent()
            if not items:
                return "No recent commands."
            return "Recent: " + ", ".join(items)

        if sub == "categories":
            cats = pal.categories()
            if not cats:
                return "No categories."
            return "Categories: " + ", ".join(cats)

        if sub == "register":
            # re-parse: "register <cmd> <desc...>"
            after = args.strip().split(maxsplit=2)  # ["register", "<cmd>", "<desc>"]
            if len(after) < 3:
                return "Usage: /palette register <cmd> <desc>"
            cmd, desc = after[1], after[2]
            pal.register(cmd, desc)
            return f"Registered palette entry '{cmd}'."

        if sub == "summary":
            return json.dumps(pal.summary(), indent=2)

        return "Usage: /palette [search <query> | recent | categories | register <cmd> <desc>]"

    registry.register(SlashCommand("palette", "Command palette operations", palette_handler))

    # ------------------------------------------------------------------ #
    # /shortcut-train                                                      #
    # ------------------------------------------------------------------ #

    async def train_handler(args: str) -> str:
        import json

        trainer = _trainer()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else "quiz"

        if sub == "quiz":
            count = 5
            if len(parts) > 1:
                try:
                    count = int(parts[1])
                except ValueError:
                    return "Usage: /shortcut-train quiz [count]"
            questions = trainer.generate_quiz(count)
            if not questions:
                return "No shortcuts available for quiz."
            lines = ["Quiz:"]
            for i, q in enumerate(questions, 1):
                lines.append(f"  {i}. What keys for '{q.command}'?  (hint: {q.hint})")
            return "\n".join(lines)

        if sub == "progress":
            items = trainer.progress()
            if not items:
                return "No training progress yet."
            lines = ["Training progress:"]
            for p in items:
                acc = (p.correct / p.attempts * 100) if p.attempts else 0
                lines.append(f"  {p.shortcut_keys}: {p.correct}/{p.attempts} ({acc:.0f}%)")
            return "\n".join(lines)

        if sub == "accuracy":
            acc = trainer.accuracy()
            return f"Overall accuracy: {acc * 100:.1f}%"

        if sub == "weakest":
            items = trainer.weakest()
            if not items:
                return "No training data yet."
            lines = ["Weakest shortcuts:"]
            for p in items:
                acc = (p.correct / p.attempts * 100) if p.attempts else 0
                lines.append(f"  {p.shortcut_keys}: {p.correct}/{p.attempts} ({acc:.0f}%)")
            return "\n".join(lines)

        if sub == "summary":
            return json.dumps(trainer.summary(), indent=2)

        return "Usage: /shortcut-train [quiz [count] | progress | accuracy | weakest]"

    registry.register(SlashCommand("shortcut-train", "Shortcut training and quizzes", train_handler))
