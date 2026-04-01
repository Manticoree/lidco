"""Admin controls for enterprise management."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdminAction:
    """Record of an admin action."""

    action: str
    target: str
    admin_id: str = ""
    reason: str = ""
    timestamp: float = 0.0


class AdminControls:
    """Enterprise admin controls for plugins, MCP servers, and models."""

    def __init__(self) -> None:
        self._disabled_plugins: dict[str, str] = {}  # name -> reason
        self._denied_mcp: dict[str, str] = {}  # name -> reason
        self._restricted_models: dict[str, str] = {}  # name -> reason
        self._audit: list[AdminAction] = []

    def disable_plugin(self, plugin_name: str, reason: str = "") -> None:
        """Disable a plugin."""
        self._disabled_plugins[plugin_name] = reason
        self._audit.append(AdminAction(
            action="disable_plugin",
            target=plugin_name,
            reason=reason,
            timestamp=time.time(),
        ))

    def enable_plugin(self, plugin_name: str) -> None:
        """Re-enable a plugin."""
        self._disabled_plugins.pop(plugin_name, None)
        self._audit.append(AdminAction(
            action="enable_plugin",
            target=plugin_name,
            timestamp=time.time(),
        ))

    def is_plugin_disabled(self, plugin_name: str) -> bool:
        """Check if a plugin is disabled."""
        return plugin_name in self._disabled_plugins

    def disabled_plugins(self) -> list[str]:
        """Return list of disabled plugin names."""
        return list(self._disabled_plugins)

    def deny_mcp_server(self, server_name: str, reason: str = "") -> None:
        """Deny an MCP server."""
        self._denied_mcp[server_name] = reason
        self._audit.append(AdminAction(
            action="deny_mcp_server",
            target=server_name,
            reason=reason,
            timestamp=time.time(),
        ))

    def allow_mcp_server(self, server_name: str) -> None:
        """Allow a previously denied MCP server."""
        self._denied_mcp.pop(server_name, None)
        self._audit.append(AdminAction(
            action="allow_mcp_server",
            target=server_name,
            timestamp=time.time(),
        ))

    def is_mcp_denied(self, server_name: str) -> bool:
        """Check if an MCP server is denied."""
        return server_name in self._denied_mcp

    def restrict_model(self, model_name: str, reason: str = "") -> None:
        """Restrict a model."""
        self._restricted_models[model_name] = reason
        self._audit.append(AdminAction(
            action="restrict_model",
            target=model_name,
            reason=reason,
            timestamp=time.time(),
        ))

    def unrestrict_model(self, model_name: str) -> None:
        """Remove model restriction."""
        self._restricted_models.pop(model_name, None)
        self._audit.append(AdminAction(
            action="unrestrict_model",
            target=model_name,
            timestamp=time.time(),
        ))

    def is_model_restricted(self, model_name: str) -> bool:
        """Check if a model is restricted."""
        return model_name in self._restricted_models

    def audit_log(self) -> list[AdminAction]:
        """Return all admin actions."""
        return list(self._audit)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"AdminControls: {len(self._disabled_plugins)} disabled plugins, "
            f"{len(self._denied_mcp)} denied MCP servers, "
            f"{len(self._restricted_models)} restricted models, "
            f"{len(self._audit)} audit entries"
        ]
        if self._disabled_plugins:
            lines.append("Disabled plugins:")
            for name, reason in self._disabled_plugins.items():
                lines.append(f"  {name}" + (f" ({reason})" if reason else ""))
        if self._denied_mcp:
            lines.append("Denied MCP servers:")
            for name, reason in self._denied_mcp.items():
                lines.append(f"  {name}" + (f" ({reason})" if reason else ""))
        if self._restricted_models:
            lines.append("Restricted models:")
            for name, reason in self._restricted_models.items():
                lines.append(f"  {name}" + (f" ({reason})" if reason else ""))
        return "\n".join(lines)
