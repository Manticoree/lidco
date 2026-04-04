"""
Q306 CLI commands — /monorepo, /affected, /dep-graph, /publish

Registered via register_q306_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q306_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q306 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /monorepo — Detect monorepo tool and list packages
    # ------------------------------------------------------------------
    async def monorepo_handler(args: str) -> str:
        """
        Usage: /monorepo [path]
               /monorepo detect [path]
               /monorepo packages [path]
               /monorepo config [path]
        """
        from lidco.monorepo.detector import PackageDetector

        parts = shlex.split(args) if args.strip() else []
        detector = PackageDetector()

        subcmd = parts[0].lower() if parts else "detect"
        root = parts[1] if len(parts) > 1 else (parts[0] if parts and parts[0] not in ("detect", "packages", "config") else ".")

        if subcmd in ("detect", ) or (parts and parts[0] not in ("detect", "packages", "config")):
            info = detector.detect(root)
            tool = info.tool or "none"
            pkg_count = len(info.packages)
            pkg_names = ", ".join(p.name for p in info.packages[:10])
            more = f" (+{pkg_count - 10} more)" if pkg_count > 10 else ""
            return (
                f"Monorepo tool: {tool}\n"
                f"Root: {info.root}\n"
                f"Packages ({pkg_count}): {pkg_names}{more}"
            )

        if subcmd == "packages":
            packages = detector.find_packages(root)
            if not packages:
                return "No packages found."
            lines = [f"Found {len(packages)} package(s):"]
            for p in packages:
                lines.append(f"  {p.name} ({p.version}) — {p.path}")
            return "\n".join(lines)

        if subcmd == "config":
            config = detector.workspace_config(root)
            if not config:
                return "No workspace config found."
            return json.dumps(config, indent=2)

        return f"Unknown subcommand '{subcmd}'. Use detect/packages/config."

    registry.register_async("monorepo", "Detect monorepo tool and list workspace packages", monorepo_handler)

    # ------------------------------------------------------------------
    # /affected — Find affected packages from changed files
    # ------------------------------------------------------------------
    async def affected_handler(args: str) -> str:
        """
        Usage: /affected <file1> [file2] ...
        """
        from lidco.monorepo.affected import AffectedFinder
        from lidco.monorepo.detector import PackageDetector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /affected <file1> [file2] ...\n"
                "Lists packages affected by the given changed files."
            )

        detector = PackageDetector()
        packages = detector.find_packages(".")

        finder = AffectedFinder()
        for pkg in packages:
            finder.add_package(pkg.name, pkg.path, pkg.dependencies)

        affected = finder.find_affected(parts)
        if not affected:
            return "No packages affected by the given files."

        return f"Affected packages ({len(affected)}):\n" + "\n".join(f"  {a}" for a in affected)

    registry.register_async("affected", "Find packages affected by changed files", affected_handler)

    # ------------------------------------------------------------------
    # /dep-graph — Workspace dependency graph analysis
    # ------------------------------------------------------------------
    async def dep_graph_handler(args: str) -> str:
        """
        Usage: /dep-graph [cycles|consistency|mermaid|order]
        """
        from lidco.monorepo.depgraph import DependencyGraphV2
        from lidco.monorepo.detector import PackageDetector

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "order"

        detector = PackageDetector()
        packages = detector.find_packages(".")

        graph = DependencyGraphV2()
        for pkg in packages:
            graph.add_package(pkg.name, pkg.dependencies)

        if subcmd == "cycles":
            cycles = graph.detect_circular()
            if not cycles:
                return "No circular dependencies detected."
            lines = [f"Found {len(cycles)} cycle(s):"]
            for c in cycles:
                lines.append(f"  {' -> '.join(c)}")
            return "\n".join(lines)

        if subcmd == "consistency":
            issues = graph.version_consistency()
            if not issues:
                return "All dependency versions are consistent."
            lines = [f"Found {len(issues)} inconsistency(ies):"]
            for i in issues:
                vers = ", ".join(f"{k}={v}" for k, v in sorted(i.versions.items()))
                lines.append(f"  {i.dependency}: {vers}")
            return "\n".join(lines)

        if subcmd == "mermaid":
            return graph.as_mermaid()

        if subcmd == "order":
            order = graph.topological_order()
            if not order:
                return "No packages found."
            return "Topological order:\n" + "\n".join(f"  {i+1}. {n}" for i, n in enumerate(order))

        return f"Unknown subcommand '{subcmd}'. Use cycles/consistency/mermaid/order."

    registry.register_async("dep-graph", "Workspace dependency graph analysis", dep_graph_handler)

    # ------------------------------------------------------------------
    # /publish — Publish orchestration
    # ------------------------------------------------------------------
    async def publish_handler(args: str) -> str:
        """
        Usage: /publish order
               /publish bump <major|minor|patch>
               /publish canary
               /publish status
               /publish rollback
        """
        from lidco.monorepo.detector import PackageDetector
        from lidco.monorepo.publish import PublishOrchestrator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /publish <subcommand>\n"
                "  order               publish order (deps first)\n"
                "  bump <type>         bump all versions (major/minor/patch)\n"
                "  canary              generate canary versions\n"
                "  status              show current package status\n"
                "  rollback            show rollback plan"
            )

        subcmd = parts[0].lower()

        detector = PackageDetector()
        packages = detector.find_packages(".")

        orch = PublishOrchestrator()
        for pkg in packages:
            orch.add_package(pkg.name, pkg.version, pkg.dependencies)

        if subcmd == "order":
            order = orch.publish_order()
            if not order:
                return "No packages to publish."
            return "Publish order:\n" + "\n".join(f"  {i+1}. {n}" for i, n in enumerate(order))

        if subcmd == "bump":
            bump_type = parts[1] if len(parts) > 1 else "patch"
            if bump_type not in ("major", "minor", "patch"):
                return f"Invalid bump type '{bump_type}'. Use major/minor/patch."
            result = orch.bump_all(bump_type)
            lines = [f"Bumped all versions ({bump_type}):"]
            for name, ver in sorted(result.items()):
                lines.append(f"  {name} -> {ver}")
            return "\n".join(lines)

        if subcmd == "canary":
            result = orch.canary_versions()
            lines = ["Canary versions:"]
            for name, ver in sorted(result.items()):
                lines.append(f"  {name} -> {ver}")
            return "\n".join(lines)

        if subcmd == "status":
            st = orch.status()
            lines = [f"Total packages: {st['total']}"]
            for name, info in sorted(st["packages"].items()):
                lines.append(f"  {name}: {info['version']} (published={info['published']})")
            return "\n".join(lines)

        if subcmd == "rollback":
            plan = orch.rollback_plan()
            if not plan:
                return "No version history — nothing to roll back."
            lines = [f"Rollback history ({len(plan)} snapshot(s)):"]
            for i, snap in enumerate(plan):
                versions = ", ".join(f"{k}={v}" for k, v in sorted(snap.items()))
                lines.append(f"  {i+1}. {versions}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use order/bump/canary/status/rollback."

    registry.register_async("publish", "Monorepo publish orchestration", publish_handler)
