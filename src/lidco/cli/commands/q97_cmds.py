"""
Q97 CLI commands — /run, /watch, /config, /template

Registered via register_q97_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q97_commands(registry) -> None:
    """Register Q97 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /run — Execute shell commands
    # ------------------------------------------------------------------
    async def run_handler(args: str) -> str:
        """
        Usage: /run <command> [--timeout N] [--cwd PATH] [--env K=V ...]
        """
        from lidco.execution.process_runner import ProcessRunner

        if not args.strip():
            return (
                "Usage: /run <command> [options]\n"
                "Options:\n"
                "  --timeout N    timeout in seconds (default 60)\n"
                "  --cwd PATH     working directory\n"
                "  --env K=V      environment variable\n"
                "Example: /run ls -la --timeout 10"
            )

        parts = shlex.split(args)
        timeout = 60.0
        cwd = None
        env: dict[str, str] = {}
        cmd_parts: list[str] = []
        i = 0
        while i < len(parts):
            tok = parts[i]
            if tok == "--timeout" and i + 1 < len(parts):
                i += 1
                try:
                    timeout = float(parts[i])
                except ValueError:
                    return f"Error: --timeout must be a number, got '{parts[i]}'"
            elif tok == "--cwd" and i + 1 < len(parts):
                i += 1
                cwd = parts[i]
            elif tok == "--env" and i + 1 < len(parts):
                i += 1
                k, _, v = parts[i].partition("=")
                env[k.strip()] = v
            else:
                cmd_parts.append(tok)
            i += 1

        if not cmd_parts:
            return "Error: command is empty."

        cmd = " ".join(cmd_parts)
        try:
            runner = ProcessRunner(default_timeout=timeout, default_cwd=cwd)
            result = runner.run(cmd, env=env or None)
            return result.format_summary()
        except Exception as exc:
            return f"Error: {exc}"

    registry.register_async("run", "Execute shell commands with timeout and env control", run_handler)

    # ------------------------------------------------------------------
    # /watch — File system watcher
    # ------------------------------------------------------------------

    _watch_state: dict[str, object] = {}

    async def watch_handler(args: str) -> str:
        """
        Usage: /watch start <dir> [--pattern *.py] [--interval N]
               /watch stop
               /watch status
               /watch events
        """
        from lidco.watch.file_watcher import FileWatcher, WatchEvent

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "status"

        if subcmd == "start":
            if len(parts) < 2:
                return "Error: specify directory to watch."
            watch_dir = parts[1]
            pattern = "*.py"
            interval = 1.0
            i = 2
            while i < len(parts):
                if parts[i] == "--pattern" and i + 1 < len(parts):
                    i += 1
                    pattern = parts[i]
                elif parts[i] == "--interval" and i + 1 < len(parts):
                    i += 1
                    try:
                        interval = float(parts[i])
                    except ValueError:
                        pass
                i += 1

            events_log: list[str] = []

            watcher = FileWatcher(
                paths=[watch_dir],
                poll_interval=interval,
                debounce=interval / 2,
            )
            watcher.register_handler(
                pattern,
                lambda evt: events_log.append(str(evt)),
            )
            watcher.start()
            _watch_state["watcher"] = watcher
            _watch_state["events"] = events_log
            return f"Watching {watch_dir} for {pattern} (interval={interval}s). Use /watch events or /watch stop."

        if subcmd == "stop":
            watcher = _watch_state.get("watcher")
            if watcher is None:
                return "No active watcher."
            watcher.stop()  # type: ignore[union-attr]
            _watch_state.clear()
            return "Watcher stopped."

        if subcmd == "events":
            events_log = _watch_state.get("events", [])
            if not events_log:
                return "No events recorded."
            return "\n".join(events_log[-20:])

        if subcmd == "status":
            watcher = _watch_state.get("watcher")
            if watcher is None:
                return "No active watcher. Use /watch start <dir>."
            is_running = watcher.running  # type: ignore[union-attr]
            events_log = _watch_state.get("events", [])
            return f"Watcher running: {is_running}  Events: {len(events_log)}"

        return (
            "Usage: /watch <subcommand>\n"
            "  start <dir> [--pattern GLOB] [--interval N]  start watching\n"
            "  stop                                          stop watcher\n"
            "  events                                        show recent events\n"
            "  status                                        show watcher status"
        )

    registry.register_async("watch", "Watch file system for changes", watch_handler)

    # ------------------------------------------------------------------
    # /config — Manage LIDCO configuration
    # ------------------------------------------------------------------
    async def config_handler(args: str) -> str:
        """
        Usage: /config get <key>
               /config set <key> <value>
               /config list
               /config save
               /config reload
        """
        from lidco.core.config_manager import ConfigManager

        if "manager" not in _config_state:
            _config_state["manager"] = ConfigManager()

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "list"
        mgr: ConfigManager = _config_state["manager"]  # type: ignore[assignment]

        if subcmd == "get":
            if len(parts) < 2:
                return "Error: key required. Usage: /config get <key>"
            key = parts[1]
            val = mgr.get(key)
            if val is None:
                return f"Key '{key}' not found."
            return f"{key} = {val!r}"

        if subcmd == "set":
            if len(parts) < 3:
                return "Error: Usage: /config set <key> <value>"
            key = parts[1]
            val_str = parts[2]
            # Try to coerce
            from lidco.core.config_manager import _coerce
            mgr.set(key, _coerce(val_str))
            return f"Set {key} = {mgr.get(key)!r}"

        if subcmd == "list":
            cfg = mgr.all()
            if not cfg:
                return "No configuration loaded."
            lines = []
            def flatten(d: dict, prefix: str = "") -> None:
                for k, v in d.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, dict):
                        flatten(v, full_key)
                    else:
                        lines.append(f"  {full_key} = {v!r}")
            flatten(cfg)
            return "Configuration:\n" + "\n".join(sorted(lines))

        if subcmd == "save":
            path = mgr.save()
            return f"Config saved to {path}"

        if subcmd == "reload":
            mgr.reload()
            return "Config reloaded."

        return (
            "Usage: /config <subcommand>\n"
            "  get <key>        get a config value\n"
            "  set <key> <val>  set a config value (in-memory)\n"
            "  list             show all config keys\n"
            "  save             persist to .lidco/config.json\n"
            "  reload           reload from disk"
        )

    _config_state: dict[str, object] = {}
    registry.register_async("config", "Manage LIDCO configuration", config_handler)

    # ------------------------------------------------------------------
    # /template — Render templates
    # ------------------------------------------------------------------
    async def template_handler(args: str) -> str:
        """
        Usage: /template render <template_string> [--var K=V ...]
               /template file <path> [--var K=V ...]
               /template test
        """
        from lidco.templates.engine import TemplateEngine, TemplateError

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /template <subcommand>\n"
                "  render '<template>' [--var K=V ...]  render a template string\n"
                "  file <path> [--var K=V ...]          render a template file\n"
                "  test                                 run a quick demo\n"
                "Example: /template render 'Hello {{ name }}!' --var name=World"
            )

        subcmd = parts[0].lower()
        engine = TemplateEngine()

        # Parse --var flags
        def parse_vars(part_list: list[str]) -> tuple[list[str], dict[str, str]]:
            remaining: list[str] = []
            variables: dict[str, str] = {}
            i = 0
            while i < len(part_list):
                if part_list[i] == "--var" and i + 1 < len(part_list):
                    i += 1
                    k, _, v = part_list[i].partition("=")
                    variables[k.strip()] = v
                else:
                    remaining.append(part_list[i])
                i += 1
            return remaining, variables

        if subcmd == "render":
            remaining, variables = parse_vars(parts[1:])
            if not remaining:
                return "Error: template string required."
            template_str = " ".join(remaining)
            try:
                return engine.render(template_str, variables)
            except TemplateError as exc:
                return f"Template error: {exc}"

        if subcmd == "file":
            remaining, variables = parse_vars(parts[1:])
            if not remaining:
                return "Error: file path required."
            try:
                return engine.render_file(remaining[0], variables)
            except Exception as exc:
                return f"Error: {exc}"

        if subcmd == "test":
            demo = (
                "Hello {{ name }}!\n"
                "{% if show_list %}\n"
                "Items:\n"
                "{% for item in items %}  - {{ item }}\n{% endfor %}"
                "{% endif %}\n"
                "Done."
            )
            ctx = {"name": "World", "show_list": True, "items": ["alpha", "beta", "gamma"]}
            try:
                return engine.render(demo, ctx)
            except TemplateError as exc:
                return f"Template error: {exc}"

        return f"Unknown subcommand '{subcmd}'. Use 'render', 'file', or 'test'."

    registry.register_async("template", "Render Jinja2-like templates", template_handler)
