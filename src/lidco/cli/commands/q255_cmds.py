"""Q255 CLI commands: /dep-graph, /resolve-deps, /license-audit, /plan-updates."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q255 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /dep-graph
    # ------------------------------------------------------------------

    async def dep_graph_handler(args: str) -> str:
        from lidco.depgraph.builder import DepGraphBuilder, DepNode, DepEdge

        builder = DepGraphBuilder()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /dep-graph add <name> [version] [--transitive]"
            tokens = rest.split()
            name = tokens[0]
            version = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("--") else ""
            direct = "--transitive" not in tokens
            builder.add_node(DepNode(name=name, version=version, direct=direct))
            return f"Added {name}" + (f" {version}" if version else "") + (" (transitive)" if not direct else "")

        if sub == "show":
            data = builder.to_dict()
            nodes = data["nodes"]
            edges = data["edges"]
            return f"{len(nodes)} node(s), {len(edges)} edge(s)"

        if sub == "link":
            if not rest:
                return "Usage: /dep-graph link <source> <target> [constraint]"
            tokens = rest.split()
            source = tokens[0]
            target = tokens[1] if len(tokens) > 1 else ""
            constraint = tokens[2] if len(tokens) > 2 else ""
            if not target:
                return "Usage: /dep-graph link <source> <target> [constraint]"
            builder.add_edge(DepEdge(source=source, target=target, version_constraint=constraint))
            return f"Linked {source} -> {target}" + (f" ({constraint})" if constraint else "")

        return (
            "Usage: /dep-graph <subcommand>\n"
            "  add <name> [version] [--transitive] — add a dependency node\n"
            "  show                                — show graph stats\n"
            "  link <src> <tgt> [constraint]       — add an edge"
        )

    # ------------------------------------------------------------------
    # /resolve-deps
    # ------------------------------------------------------------------

    async def resolve_deps_handler(args: str) -> str:
        from lidco.depgraph.builder import DepGraphBuilder, DepNode, DepEdge
        from lidco.depgraph.resolver import VersionResolver

        builder = DepGraphBuilder()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "conflicts":
            # Demo: parse "pkg1:>=1.0 pkg1:>=2.0" style
            if not rest:
                return "No edges to analyse — provide constraints as pkg:constraint pairs."
            tokens = rest.split()
            for tok in tokens:
                if ":" in tok:
                    target, constraint = tok.split(":", 1)
                    builder.add_node(DepNode(name=target))
                    builder.add_edge(DepEdge(source="root", target=target, version_constraint=constraint))
            resolver = VersionResolver(builder)
            conflicts = resolver.find_conflicts()
            if not conflicts:
                return "No conflicts found."
            lines = [f"{len(conflicts)} conflict(s):"]
            for c in conflicts:
                lines.append(f"  {c['name']}: {', '.join(c['constraints'])}")
            return "\n".join(lines)

        if sub == "resolve":
            if not rest:
                return "Usage: /resolve-deps resolve <name:version> ..."
            constraints: list[dict] = []
            for tok in rest.split():
                if ":" in tok:
                    name, version = tok.split(":", 1)
                    constraints.append({"name": name, "version": version})
            resolver = VersionResolver(builder)
            resolved = resolver.resolve(constraints)
            if not resolved:
                return "Nothing to resolve."
            lines = ["Resolved:"]
            for name, ver in resolved.items():
                lines.append(f"  {name} = {ver}")
            return "\n".join(lines)

        if sub == "upgrades":
            if not rest:
                return "No packages to suggest upgrades for."
            for tok in rest.split():
                if ":" in tok:
                    name, version = tok.split(":", 1)
                else:
                    name, version = tok, "0.0.1"
                builder.add_node(DepNode(name=name, version=version))
            resolver = VersionResolver(builder)
            suggestions = resolver.suggest_upgrades()
            if not suggestions:
                return "No upgrade suggestions."
            lines = [f"{len(suggestions)} suggestion(s):"]
            for s in suggestions:
                lines.append(f"  {s['name']}: {s['current']} -> {s['suggested']}")
            return "\n".join(lines)

        return (
            "Usage: /resolve-deps <subcommand>\n"
            "  conflicts <pkg:constraint ...> — find conflicting constraints\n"
            "  resolve <name:version ...>     — resolve to latest versions\n"
            "  upgrades <name:version ...>    — suggest version bumps"
        )

    # ------------------------------------------------------------------
    # /license-audit
    # ------------------------------------------------------------------

    async def license_audit_handler(args: str) -> str:
        from lidco.depgraph.license import LicenseAnalyzer, LicenseInfo

        analyzer = LicenseAnalyzer()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /license-audit add <package> <license> [category]"
            tokens = rest.split()
            pkg = tokens[0]
            lic = tokens[1] if len(tokens) > 1 else "unknown"
            cat = tokens[2] if len(tokens) > 2 else "unknown"
            analyzer.add(LicenseInfo(package=pkg, license=lic, category=cat))
            return f"Added {pkg}: {lic} ({cat})"

        if sub == "check":
            if not rest:
                return "Usage: /license-audit check <project-license>"
            incompatible = analyzer.check_compatibility(rest.strip())
            if not incompatible:
                return "All licenses compatible."
            return f"Incompatible: {', '.join(incompatible)}"

        if sub == "sbom":
            sbom = analyzer.generate_sbom()
            return f"SBOM: {sbom['total']} package(s), format={sbom['format']}"

        if sub == "summary":
            return analyzer.summary()

        return (
            "Usage: /license-audit <subcommand>\n"
            "  add <pkg> <license> [category] — register a license\n"
            "  check <project-license>        — check compatibility\n"
            "  sbom                           — generate SBOM\n"
            "  summary                        — license summary"
        )

    # ------------------------------------------------------------------
    # /plan-updates
    # ------------------------------------------------------------------

    async def plan_updates_handler(args: str) -> str:
        from lidco.depgraph.update_planner import UpdatePlanner

        planner = UpdatePlanner()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "plan":
            if not rest:
                return "Usage: /plan-updates plan <pkg:current:target> ..."
            updates: list[dict] = []
            for tok in rest.split():
                pieces = tok.split(":")
                if len(pieces) >= 3:
                    updates.append({"package": pieces[0], "current": pieces[1], "target": pieces[2]})
            if not updates:
                return "No valid updates parsed."
            plans = planner.plan(updates)
            return planner.summary(plans)

        if sub == "risk":
            if not rest:
                return "Usage: /plan-updates risk <pkg> <current> <target>"
            tokens = rest.split()
            if len(tokens) < 3:
                return "Usage: /plan-updates risk <pkg> <current> <target>"
            score = planner.risk_score(tokens[0], tokens[1], tokens[2])
            return f"Risk for {tokens[0]}: {score}"

        if sub == "rollback":
            if not rest:
                return "Usage: /plan-updates rollback <pkg:current:target> ..."
            updates_list: list[dict] = []
            for tok in rest.split():
                pieces = tok.split(":")
                if len(pieces) >= 3:
                    updates_list.append({"package": pieces[0], "current": pieces[1], "target": pieces[2]})
            if not updates_list:
                return "No valid updates parsed."
            plans = planner.plan(updates_list)
            rollbacks = planner.rollback_plan(plans)
            lines = [f"{len(rollbacks)} rollback(s):"]
            for r in rollbacks:
                lines.append(f"  {r['package']}: {r['from']} -> {r['to']}")
            return "\n".join(lines)

        return (
            "Usage: /plan-updates <subcommand>\n"
            "  plan <pkg:cur:tgt ...>     — plan updates with risk\n"
            "  risk <pkg> <cur> <tgt>     — compute risk score\n"
            "  rollback <pkg:cur:tgt ...> — generate rollback plan"
        )

    registry.register(SlashCommand("dep-graph", "Build and inspect dependency graphs", dep_graph_handler))
    registry.register(SlashCommand("resolve-deps", "Resolve dependency version conflicts", resolve_deps_handler))
    registry.register(SlashCommand("license-audit", "Audit dependency licenses", license_audit_handler))
    registry.register(SlashCommand("plan-updates", "Plan dependency updates with risk", plan_updates_handler))
