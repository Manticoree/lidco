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

        # Determine which config files to watch (in load order)
        project = project_dir or Path.cwd()
        self._watch_paths: list[Path] = [
            Path.home() / ".lidco" / "config.yaml",
            project / ".lidco" / "config.yaml",
        ]
        # Record initial mtimes so we only react to actual changes
        self._mtimes: dict[str, float] = {
            str(p): self._mtime(p) for p in self._watch_paths
        }

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
        changed = False
        for path in self._watch_paths:
            key = str(path)
            new_mtime = self._mtime(path)
            if new_mtime != self._mtimes.get(key, 0.0):
                self._mtimes[key] = new_mtime
                changed = True

        if not changed:
            return

        logger.info("Config file changed — hot-reloading")
        try:
            from lidco.core.config import load_config
            new_config = load_config(self._session.project_dir)
            self._apply(new_config)
        except Exception as exc:
            logger.warning("Failed to reload config: %s", exc)

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
