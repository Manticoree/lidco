"""CLI commands for Q179 — Multi-Repo & Monorepo Support."""

from __future__ import annotations

import os

from lidco.cli.commands.registry import SlashCommand


def register_q179_commands(registry) -> None:
    """Register /workspace, /search-all, /cross-deps, /shared-config."""

    from lidco.workspace.detector import WorkspaceDetector
    from lidco.workspace.cross_search import CrossRepoSearch
    from lidco.workspace.cross_deps import CrossRepoDeps
    from lidco.workspace.shared_config import SharedConfigResolver

    async def workspace_handler(args: str) -> str:
        path = args.strip() or os.getcwd()
        detector = WorkspaceDetector()
        info = detector.detect(path)
        lines = [
            f"Workspace type: {info.workspace_type}",
            f"Root: {info.root}",
            f"Packages ({len(info.packages)}):",
        ]
        for pkg in info.packages:
            dep_info = f" (deps: {', '.join(pkg.deps)})" if pkg.deps else ""
            lines.append(f"  - {pkg.name}{dep_info}")
        if not info.packages:
            lines.append("  (none detected)")
        return "\n".join(lines)

    async def search_all_handler(args: str) -> str:
        parts = args.strip().split()
        if not parts:
            return "Usage: /search-all <query> [repo_path ...]"
        query = parts[0]
        repos = parts[1:] if len(parts) > 1 else [os.getcwd()]
        searcher = CrossRepoSearch()
        results = searcher.search(query, repos)
        if not results:
            return f"No results for '{query}'."
        lines = [f"Found {len(results)} result(s) for '{query}':"]
        for r in results[:50]:
            lines.append(f"  {r.repo}/{r.file}:{r.line}  {r.match}")
        if len(results) > 50:
            lines.append(f"  ... and {len(results) - 50} more")
        return "\n".join(lines)

    async def cross_deps_handler(args: str) -> str:
        path = args.strip() or os.getcwd()
        detector = WorkspaceDetector()
        info = detector.detect(path)
        if not info.packages:
            return "No packages detected. Run /workspace first."
        builder = CrossRepoDeps()
        graph = builder.build_graph(info.packages)
        cycles = graph.find_circular()
        lines = [graph.render()]
        if cycles:
            lines.append("")
            lines.append(f"Circular dependencies ({len(cycles)}):")
            for c in cycles:
                lines.append(f"  {' -> '.join(c)} -> {c[0]}")
        return "\n".join(lines)

    async def shared_config_handler(args: str) -> str:
        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /shared-config <workspace_root> <package_path>"
        ws_root, pkg_path = parts[0], parts[1]
        resolver = SharedConfigResolver()
        config = resolver.resolve(ws_root, pkg_path)
        if not config:
            return "No configuration found."
        lines = ["Resolved configuration:"]
        for key, value in sorted(config.items()):
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    registry.register(SlashCommand("workspace", "Detect workspace type and list packages", workspace_handler))
    registry.register(SlashCommand("search-all", "Search across all repos/packages", search_all_handler))
    registry.register(SlashCommand("cross-deps", "Show cross-package dependency graph", cross_deps_handler))
    registry.register(SlashCommand("shared-config", "Resolve merged workspace+package config", shared_config_handler))
