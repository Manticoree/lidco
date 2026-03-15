"""Background config file watcher for hot-reloading LIDCO configuration.

Polls config file mtimes every ``interval`` seconds.  When a change is
detected it reloads the full config stack and applies mutable fields to the
live session without a restart.

Mutable fields (applied immediately):
  llm.default_model, llm.temperature, llm.max_tokens, llm.streaming
  agents.* (auto_review, auto_plan, max_review_iterations, agent_timeout, etc.)
  cli.*, memory.max_entries

Restart-required fields (a warning is emitted instead):
  rag.* (store path, embedding model)
  memory.enabled / memory.auto_save (affects store init)
  llm_providers.* (custom endpoint registration)

Usage::

    reloader = ConfigReloader(session, project_dir=Path.cwd())
    reloader.start()
    ...
    reloader.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from lidco.core.config import LidcoConfig
    from lidco.core.session import Session

logger = logging.getLogger(__name__)

# Fields that require a full restart — we warn but do not apply them live
_RESTART_SECTIONS = frozenset({"rag", "llm_providers"})


class ConfigReloader:
    """Background thread that polls config files and hot-reloads mutable settings.

    Args:
        session: The live :class:`~lidco.core.session.Session` to update.
        project_dir: Project root (used to locate ``.lidco/config.yaml``).
        interval: Poll interval in seconds (default 30).
        status_callback: Optional callable ``(message: str) -> None`` to
            surface reload notifications (e.g., to the CLI status bar).
    """

    def __init__(
        self,
        session: "Session",
        project_dir: Path | None = None,
        interval: float = 30.0,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._interval = interval
        self._status_callback = status_callback
        self._running = False
        self._thread: threading.Thread | None = None
        # Q54/363: protect _mtimes / _agent_mtimes from background-thread race
        self._lock = threading.Lock()

        # Determine which config files to watch (in load order)
        project = project_dir or Path.cwd()
        self._project_dir = project
        self._watch_paths: list[Path] = [
            Path.home() / ".lidco" / "config.yaml",
            project / ".lidco" / "config.yaml",
        ]
        # MCP config files watched separately
        self._mcp_paths: list[Path] = [
            Path.home() / ".lidco" / "mcp.json",
            project / ".lidco" / "mcp.json",
        ]
        # Agent definition directories — watch for .yaml/.yml/.md changes
        self._agent_dirs: list[Path] = [
            Path.home() / ".lidco" / "agents",
            project / ".lidco" / "agents",
        ]
        # Record initial mtimes so we only react to actual changes
        all_watched = self._watch_paths + self._mcp_paths
        self._mtimes: dict[str, float] = {
            str(p): self._mtime(p) for p in all_watched
        }
        # Track agent file mtimes (glob on each poll)
        self._agent_mtimes: dict[str, float] = self._scan_agent_files()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="config-reloader")
        self._thread.start()
        logger.debug("Config reloader started (interval=%ss)", self._interval)

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _scan_agent_files(self) -> dict[str, float]:
        """Return a dict of {filepath: mtime} for all agent definition files."""
        result: dict[str, float] = {}
        for d in self._agent_dirs:
            if d.is_dir():
                for ext in ("*.yaml", "*.yml", "*.md"):
                    for p in d.glob(ext):
                        result[str(p)] = self._mtime(p)
        return result

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    def _run(self) -> None:
        while self._running:
            time.sleep(self._interval)
            if not self._running:
                break
            try:
                self._check()
            except Exception as exc:
                logger.debug("Config reloader error: %s", exc)

    def _check(self) -> None:
        """Check if any config file changed and reload if so."""
        # Q54/363: hold lock while reading/writing mtime dicts to prevent race
        with self._lock:
            config_changed = False
            for path in self._watch_paths:
                key = str(path)
                new_mtime = self._mtime(path)
                if new_mtime != self._mtimes.get(key, 0.0):
                    self._mtimes[key] = new_mtime
                    config_changed = True

            mcp_changed = False
            for path in self._mcp_paths:
                key = str(path)
                new_mtime = self._mtime(path)
                if new_mtime != self._mtimes.get(key, 0.0):
                    self._mtimes[key] = new_mtime
                    mcp_changed = True

            # Check agent files
            agents_changed = False
            new_agent_mtimes = self._scan_agent_files()
            if new_agent_mtimes != self._agent_mtimes:
                agents_changed = True
                self._agent_mtimes = new_agent_mtimes

        if config_changed:
            logger.info("Config file changed — hot-reloading")
            try:
                from lidco.core.config import load_config
                new_config = load_config(self._session.project_dir)
                self._apply(new_config)
            except Exception as exc:
                logger.warning("Failed to reload config: %s", exc)

        if mcp_changed:
            logger.info("MCP config changed — hot-reloading")
            self._reload_mcp()

        if agents_changed:
            logger.info("Agent files changed — hot-reloading agents")
            self._reload_agents()

    def _reload_mcp(self) -> None:
        """Reload mcp.json and connect/disconnect changed servers."""
        manager = getattr(self._session, "mcp_manager", None)
        old_config = getattr(self._session, "mcp_config", None)
        if manager is None:
            return

        try:
            from lidco.mcp.config import load_mcp_config
            new_mcp = load_mcp_config(self._project_dir)
        except Exception as exc:
            logger.warning("Failed to reload mcp.json: %s", exc)
            return

        # Diff — find removed and added servers
        old_names: set[str] = {e.name for e in old_config.servers} if old_config else set()
        new_names: set[str] = {e.name for e in new_mcp.servers}
        removed = old_names - new_names
        added = [e for e in new_mcp.servers if e.name not in old_names]

        if not removed and not added:
            return

        # Apply changes synchronously via asyncio (we're on a background thread)
        import asyncio

        async def _apply_mcp() -> None:
            from lidco.mcp.tool_adapter import inject_mcp_tools, remove_mcp_tools
            for name in removed:
                await manager.stop_server(name)
                count = remove_mcp_tools(name, self._session.tool_registry)
                logger.info("MCP: removed server '%s' (%d tool(s) unregistered)", name, count)
            for entry in added:
                success = await manager.start_server(entry)
                if success:
                    inject_mcp_tools(manager, self._session.tool_registry)
                    logger.info("MCP: added server '%s'", entry.name)

        # Q54/364: set event loop on this background thread so coroutines
        # that call asyncio.get_event_loop() work correctly
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_apply_mcp())
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        except Exception as exc:
            logger.warning("MCP hot-reload error: %s", exc)

        self._session.mcp_config = new_mcp
        msg = f"MCP reloaded — removed: {list(removed)}, added: {[e.name for e in added]}"
        logger.info(msg)
        if self._status_callback:
            try:
                self._status_callback(msg)
            except Exception:
                pass

    def _reload_agents(self) -> None:
        """Reload YAML/Markdown agent definitions from disk."""
        registry = getattr(self._session, "agent_registry", None)
        llm = getattr(self._session, "llm", None)
        tool_registry = getattr(self._session, "tool_registry", None)
        if registry is None or llm is None or tool_registry is None:
            return
        try:
            from lidco.agents.loader import discover_yaml_agents
            agents = discover_yaml_agents(
                llm,
                tool_registry,
                search_dirs=[d for d in self._agent_dirs if d.is_dir()],
            )
            if not agents:
                return
            reloaded: list[str] = []
            for agent_obj in agents:
                name = getattr(getattr(agent_obj, "_config", None), "name", None) or getattr(agent_obj, "name", None)
                if not name:
                    continue
                existing = registry.get(name)
                old_repr = repr(getattr(existing, "_config", None)) if existing else None
                new_repr = repr(getattr(agent_obj, "_config", None))
                if old_repr != new_repr:
                    registry.register(name, agent_obj)
                    reloaded.append(name)
            if reloaded:
                msg = f"Agents reloaded: {', '.join(reloaded)}"
                logger.info(msg)
                if self._status_callback:
                    try:
                        self._status_callback(msg)
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("Failed to reload agents: %s", exc)

    def _apply(self, new: "LidcoConfig") -> None:
        """Apply changed fields from *new* config to the live session."""
        old = self._session.config
        changed_fields: list[str] = []
        restart_fields: list[str] = []

        # ── LLM mutable fields ────────────────────────────────────────────────
        if new.llm.default_model != old.llm.default_model:
            self._session.llm.set_default_model(new.llm.default_model)
            changed_fields.append(f"llm.default_model={new.llm.default_model!r}")

        # ── Agents mutable fields ─────────────────────────────────────────────
        agent_fields = (
            "auto_review", "auto_plan", "max_review_iterations",
            "agent_timeout", "default",
            "plan_critique", "plan_revise", "plan_max_revisions",
            "plan_memory", "preplan_snapshot", "debug_mode",
            "debug_hypothesis", "debug_fast_path", "auto_debug", "debug_preset",
            "coverage_gap_inject", "sbfl_inject", "web_context_inject", "web_auto_route",
        )
        for fname in agent_fields:
            if getattr(new.agents, fname) != getattr(old.agents, fname):
                changed_fields.append(f"agents.{fname}={getattr(new.agents, fname)!r}")

        # ── Restart-required sections ─────────────────────────────────────────
        for section in _RESTART_SECTIONS:
            if getattr(new, section) != getattr(old, section):
                restart_fields.append(section)

        # Replace the config object on the session
        self._session.config = new

        # Propagate to orchestrator via public setters (BaseOrchestrator no-ops
        # for fields the simple Orchestrator doesn't support)
        try:
            orch = self._session.orchestrator
            if new.agents.agent_timeout != old.agents.agent_timeout:
                orch.set_agent_timeout(new.agents.agent_timeout)
            if new.agents.auto_review != old.agents.auto_review:
                orch.set_auto_review(new.agents.auto_review)
            if new.agents.auto_plan != old.agents.auto_plan:
                orch.set_auto_plan(new.agents.auto_plan)
            if new.agents.max_review_iterations != old.agents.max_review_iterations:
                orch.set_max_review_iterations(new.agents.max_review_iterations)
            if new.agents.default != old.agents.default:
                orch.set_default_agent(new.agents.default)
            if new.agents.plan_critique != old.agents.plan_critique:
                orch.set_plan_critique(new.agents.plan_critique)
            if new.agents.plan_revise != old.agents.plan_revise:
                orch.set_plan_revise(new.agents.plan_revise)
            if new.agents.plan_max_revisions != old.agents.plan_max_revisions:
                orch.set_plan_max_revisions(new.agents.plan_max_revisions)
            if new.agents.plan_memory != old.agents.plan_memory:
                orch.set_plan_memory(new.agents.plan_memory)
            if new.agents.preplan_snapshot != old.agents.preplan_snapshot:
                orch.set_preplan_snapshot(new.agents.preplan_snapshot)
            if new.agents.preplan_ambiguity != old.agents.preplan_ambiguity:
                orch.set_preplan_ambiguity(new.agents.preplan_ambiguity)
            if new.agents.debug_mode != old.agents.debug_mode:
                orch.set_debug_mode(new.agents.debug_mode)
                self._session.debug_mode = new.agents.debug_mode
            if new.agents.debug_hypothesis != old.agents.debug_hypothesis:
                orch.set_debug_hypothesis(new.agents.debug_hypothesis)
            if new.agents.debug_fast_path != old.agents.debug_fast_path:
                orch.set_debug_fast_path(new.agents.debug_fast_path)
            if new.agents.auto_debug != old.agents.auto_debug:
                orch.set_auto_debug(new.agents.auto_debug)
            if new.agents.debug_preset != old.agents.debug_preset:
                orch.set_debug_preset(new.agents.debug_preset)
            if new.agents.coverage_gap_inject != old.agents.coverage_gap_inject:
                orch.set_coverage_gap_inject(new.agents.coverage_gap_inject)
            if new.agents.sbfl_inject != old.agents.sbfl_inject:
                orch.set_sbfl_inject(new.agents.sbfl_inject)
            if new.agents.web_context_inject != old.agents.web_context_inject:
                orch.set_web_context_inject(new.agents.web_context_inject)
            if new.agents.web_auto_route != old.agents.web_auto_route:
                orch.set_web_auto_route(new.agents.web_auto_route)
        except Exception as exc:
            logger.debug("Could not propagate changes to orchestrator: %s", exc)

        # Propagate permission mode changes
        engine = getattr(self._session, "permission_engine", None)
        if engine is not None:
            if new.permissions.mode != old.permissions.mode:
                engine.set_mode(new.permissions.mode)
                changed_fields.append(f"permissions.mode={new.permissions.mode}")

        if changed_fields:
            msg = "Config reloaded — " + ", ".join(changed_fields)
            logger.info(msg)
            if self._status_callback is not None:
                try:
                    self._status_callback(msg)
                except Exception:
                    pass

        if restart_fields:
            logger.warning(
                "Config change in section(s) %s requires restart to take effect",
                ", ".join(restart_fields),
            )
