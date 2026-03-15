"""MCP OAuth auth flow — Task 258 (stub).

Full OAuth flow deferred. Use manual bearer tokens in mcp.json for now:

  {"auth": {"type": "bearer", "token": "your-token-here"}}
"""

from __future__ import annotations


class OAuthFlow:
    """Browser-based OAuth flow for HTTP MCP servers (not yet implemented).

    Use manual tokens in mcp.json auth field instead:
      {"auth": {"type": "bearer", "token": "ghp_..."}}
    """

    async def get_token(self, server_url: str, client_id: str) -> str:
        raise NotImplementedError(
            "OAuth auto-flow is not yet implemented. "
            "Set auth.token manually in .lidco/mcp.json:\n"
            '  {"auth": {"type": "bearer", "token": "your-token"}}'
        )
