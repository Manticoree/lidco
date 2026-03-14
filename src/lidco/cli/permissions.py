"""Permission manager — bridges PermissionEngine with the interactive approval UI."""

from __future__ import annotations

from rich.console import Console

from lidco.cli.approval import Decision, ask
from lidco.core.config import PermissionsConfig
from lidco.core.permission_engine import PermissionEngine, PermissionMode


class PermissionManager:
    """Manages tool execution permissions.

    Delegates evaluation to PermissionEngine and handles interactive approval
    via the approval module. Backward compatible with the old constructor
    signature (PermissionsConfig).
    """

    def __init__(
        self,
        config_or_engine: PermissionsConfig | PermissionEngine,
        console: Console | None = None,
    ) -> None:
        if isinstance(config_or_engine, PermissionEngine):
            self._engine = config_or_engine
        else:
            self._engine = PermissionEngine(config_or_engine)
        self._console = console or Console()

    # ------------------------------------------------------------------
    # Public API (backward compatible)
    # ------------------------------------------------------------------

    def check(self, tool_name: str, params: dict) -> bool:
        """Check if a tool execution is allowed. Returns True if allowed."""
        result = self._engine.check(tool_name, params)

        if result.decision == "allow":
            return True

        if result.decision == "deny":
            self._console.print(
                f"[red]  ✗ {tool_name} denied[/red] [dim]— {result.reason}[/dim]"
            )
            return False

        # result.decision == "ask" → interactive prompt
        decision = ask(tool_name, params, result, self._console)

        if decision == Decision.ALLOW_ONCE:
            return True

        if decision == Decision.ALLOW_SESSION:
            self._engine.add_session_allow(tool_name, params)
            self._console.print(
                f"[green]  ✓ {tool_name} allowed for session[/green]"
            )
            return True

        if decision == Decision.ALLOW_ALWAYS:
            spec = self._engine._make_spec(tool_name, params)
            self._engine.add_persistent_allow(spec)
            self._console.print(
                f"[green]  ✓ {tool_name} always allowed (saved to permissions.json)[/green]"
            )
            return True

        if decision == Decision.DENY_ONCE:
            self._console.print(f"[red]  ✗ {tool_name} denied[/red]")
            return False

        if decision == Decision.DENY_ALWAYS:
            spec = self._engine._make_spec(tool_name, params)
            self._engine.add_persistent_deny(spec)
            self._console.print(
                f"[red]  ✗ {tool_name} permanently denied (saved)[/red]"
            )
            return False

        # Explain was handled inside ask(); re-ask returned actual decision
        return False

    def auto_allow(self, tool_name: str) -> None:
        """Mark a tool as auto-allowed for this session (backward compat)."""
        from lidco.core.permission_engine import RuleParser, _SessionDecision
        spec = tool_name
        parsed = RuleParser.parse(spec)
        self._engine._session_allowed.append(_SessionDecision(spec, parsed))

    def allow_all(self) -> None:
        """Auto-allow all tools for this session (backward compat)."""
        self._engine.set_mode(PermissionMode.BYPASS)

    @property
    def engine(self) -> PermissionEngine:
        return self._engine
