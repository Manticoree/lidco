"""Q208 CLI commands: /migrate, /bootstrap, /setup, /doctor."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q208 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /migrate
    # ------------------------------------------------------------------

    async def migrate_handler(args: str) -> str:
        from lidco.migrations.runner import Migration, MigrationRunner

        if "runner" not in _state:
            _state["runner"] = MigrationRunner()
        runner: MigrationRunner = _state["runner"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "up":
            results = runner.run_up(rest if rest else None)
            if not results:
                return "No pending migrations."
            lines = [f"Ran {len(results)} migration(s) up:"]
            for r in results:
                status = "OK" if r.success else f"FAILED: {r.error}"
                lines.append(f"  {r.version} — {status} ({r.duration_ms:.1f}ms)")
            return "\n".join(lines)

        if sub == "down":
            if not rest:
                return "Usage: /migrate down <version>"
            result = runner.run_down(rest)
            status = "OK" if result.success else f"FAILED: {result.error}"
            return f"Rolled back {result.version} — {status}"

        if sub == "status":
            migrations = runner.get_status()
            if not migrations:
                return "No migrations registered."
            lines = [f"{len(migrations)} migration(s):"]
            for m in migrations:
                lines.append(f"  {m.version} [{m.status.value}] {m.name}")
            return "\n".join(lines)

        if sub == "pending":
            pending = runner.pending()
            if not pending:
                return "No pending migrations."
            lines = [f"{len(pending)} pending migration(s):"]
            for m in pending:
                lines.append(f"  {m.version} — {m.name}")
            return "\n".join(lines)

        if sub == "dry-run":
            stmts = runner.dry_run(rest if rest else None)
            if not stmts:
                return "Nothing to run."
            return "\n".join(stmts)

        return (
            "Usage: /migrate <subcommand>\n"
            "  up [version]     — run migrations up\n"
            "  down <version>   — rollback one migration\n"
            "  status           — show all migrations\n"
            "  pending          — show pending migrations\n"
            "  dry-run [ver]    — preview SQL"
        )

    # ------------------------------------------------------------------
    # /bootstrap
    # ------------------------------------------------------------------

    async def bootstrap_handler(args: str) -> str:
        from lidco.bootstrap.manager import BootstrapManager, BootstrapPhase, BootstrapStep

        if "bm" not in _state:
            _state["bm"] = BootstrapManager()
        bm: BootstrapManager = _state["bm"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "run":
            results = bm.run()
            if not results:
                return "No bootstrap steps registered."
            return bm.summary()

        if sub == "status":
            return bm.summary()

        if sub == "health":
            health = bm.health_check()
            if not health:
                return "No bootstrap results yet."
            lines = ["Health check:"]
            for name, ok in health.items():
                lines.append(f"  {name}: {'OK' if ok else 'FAIL'}")
            return "\n".join(lines)

        return (
            "Usage: /bootstrap <subcommand>\n"
            "  run      — run all bootstrap steps\n"
            "  status   — show bootstrap summary\n"
            "  health   — health check"
        )

    # ------------------------------------------------------------------
    # /setup
    # ------------------------------------------------------------------

    async def setup_handler(args: str) -> str:
        from lidco.bootstrap.setup_wizard import SetupWizard

        if "wizard" not in _state:
            _state["wizard"] = SetupWizard()
        wizard: SetupWizard = _state["wizard"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "status":
            return wizard.summary()

        if sub == "test":
            ok = wizard.test_connection()
            return "Connection test: OK" if ok else "Connection test: FAILED"

        if sub == "api-key":
            if not rest:
                return "Usage: /setup api-key <key>"
            wizard.set_api_key(rest)
            return "API key configured."

        if sub == "model":
            if not rest:
                return "Usage: /setup model <name>"
            wizard.set_model(rest)
            return f"Model set to '{rest}'."

        return (
            "Usage: /setup <subcommand>\n"
            "  status          — show setup state\n"
            "  test            — test connection\n"
            "  api-key <key>   — set API key\n"
            "  model <name>    — set model"
        )

    # ------------------------------------------------------------------
    # /doctor
    # ------------------------------------------------------------------

    async def doctor_handler(args: str) -> str:
        from lidco.bootstrap.manager import BootstrapManager
        from lidco.migrations.runner import MigrationRunner

        lines = ["System doctor:"]

        # Migrations
        if "runner" in _state:
            runner: MigrationRunner = _state["runner"]  # type: ignore[assignment]
            pending = runner.pending()
            lines.append(f"  Migrations: {len(pending)} pending")
        else:
            lines.append("  Migrations: not initialized")

        # Bootstrap
        if "bm" in _state:
            bm: BootstrapManager = _state["bm"]  # type: ignore[assignment]
            ready = bm.is_ready()
            lines.append(f"  Bootstrap: {'ready' if ready else 'not ready'}")
        else:
            lines.append("  Bootstrap: not initialized")

        # Setup
        if "wizard" in _state:
            from lidco.bootstrap.setup_wizard import SetupWizard
            wizard: SetupWizard = _state["wizard"]  # type: ignore[assignment]
            complete = wizard.is_complete()
            lines.append(f"  Setup: {'complete' if complete else 'incomplete'}")
        else:
            lines.append("  Setup: not initialized")

        return "\n".join(lines)

    registry.register(SlashCommand("migrate", "Versioned migration runner", migrate_handler))
    registry.register(SlashCommand("bootstrap", "System bootstrap manager", bootstrap_handler))
    registry.register(SlashCommand("setup", "First-run setup wizard", setup_handler))
    registry.register(SlashCommand("doctor", "System health doctor", doctor_handler))
