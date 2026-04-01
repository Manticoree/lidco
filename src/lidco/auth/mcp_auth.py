"""MCP server authentication adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lidco.auth.keychain import KeychainStorage


@dataclass(frozen=True)
class MCPCredential:
    """Credential for a single MCP server."""

    server_name: str
    auth_type: str  # "oauth" | "api_key" | "basic"
    token: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MCPAuthAdapter:
    """Manage credentials for MCP servers."""

    def __init__(self, keychain: KeychainStorage | None = None) -> None:
        self._keychain = keychain or KeychainStorage()
        self._credentials: dict[str, MCPCredential] = {}

    def register_credential(
        self,
        server_name: str,
        auth_type: str,
        token: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MCPCredential:
        """Register (or overwrite) a credential for *server_name*."""
        cred = MCPCredential(
            server_name=server_name,
            auth_type=auth_type,
            token=token,
            metadata=metadata or {},
        )
        self._credentials[server_name] = cred
        if token:
            self._keychain.set(server_name, "token", token)
        return cred

    def get_credential(self, server_name: str) -> MCPCredential | None:
        """Return the credential for *server_name*, or ``None``."""
        return self._credentials.get(server_name)

    def remove_credential(self, server_name: str) -> bool:
        """Remove a credential. Return whether it existed."""
        removed = self._credentials.pop(server_name, None) is not None
        self._keychain.delete(server_name, "token")
        return removed

    def list_servers(self) -> list[str]:
        """Return sorted list of server names with credentials."""
        return sorted(self._credentials)

    def inject_env(self, server_name: str) -> dict[str, str]:
        """Return environment variables to inject for *server_name*."""
        cred = self._credentials.get(server_name)
        if cred is None:
            return {}
        env: dict[str, str] = {}
        prefix = server_name.upper().replace("-", "_")
        if cred.token:
            env[f"{prefix}_TOKEN"] = cred.token
        env[f"{prefix}_AUTH_TYPE"] = cred.auth_type
        for k, v in cred.metadata.items():
            env[f"{prefix}_{k.upper()}"] = str(v)
        return env

    def has_credential(self, server_name: str) -> bool:
        """Return True if a credential exists for *server_name*."""
        return server_name in self._credentials

    def summary(self) -> str:
        """Return a human-readable summary of registered credentials."""
        if not self._credentials:
            return "No MCP credentials registered."
        lines = [f"{len(self._credentials)} MCP credential(s):"]
        for name in sorted(self._credentials):
            cred = self._credentials[name]
            masked = "***" if cred.token else "(none)"
            lines.append(f"  {name} [{cred.auth_type}] token={masked}")
        return "\n".join(lines)
