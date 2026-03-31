"""Claude Code Plugin Compatibility Layer (Q168)."""
from __future__ import annotations

from lidco.compat.cc_manifest import CCPluginManifest, parse_cc_manifest, to_lidco_manifest
from lidco.compat.cc_mcp_adapter import CCMCPServer, parse_cc_mcp_config, to_lidco_mcp_config
from lidco.compat.cc_conventions import CCProjectConfig, scan_claude_dir
from lidco.compat.cc_hooks import CCHook, parse_cc_hooks, to_lidco_hooks

__all__ = [
    "CCPluginManifest",
    "parse_cc_manifest",
    "to_lidco_manifest",
    "CCMCPServer",
    "parse_cc_mcp_config",
    "to_lidco_mcp_config",
    "CCProjectConfig",
    "scan_claude_dir",
    "CCHook",
    "parse_cc_hooks",
    "to_lidco_hooks",
]
