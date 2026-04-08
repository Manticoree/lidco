"""
Q307 CLI commands — /codeowners, /ownership-analyze, /review-route, /knowledge-transfer

Registered via register_q307_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q307_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q307 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /codeowners — Generate CODEOWNERS file
    # ------------------------------------------------------------------
    async def codeowners_handler(args: str) -> str:
        """
        Usage: /codeowners [path]
               /codeowners generate [path]
               /codeowners show [path]
        """
        from lidco.ownership.generator import CodeownersGenerator

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "generate"
        repo_path = parts[1] if len(parts) > 1 else (
            parts[0] if parts and parts[0] not in ("generate", "show") else "."
        )

        gen = CodeownersGenerator()

        if subcmd in ("generate",) or (parts and parts[0] not in ("generate", "show")):
            result = gen.generate_from_git(repo_path)
            if not result.entries:
                return "No ownership data found. Ensure git history exists."
            text = result.render()
            unmapped = ""
            if result.unmapped_authors:
                unmapped = (
                    f"\nUnmapped authors: {', '.join(result.unmapped_authors)}"
                )
            return f"Generated CODEOWNERS ({len(result.entries)} entries):\n{text}{unmapped}"

        if subcmd == "show":
            result = gen.generate_from_git(repo_path)
            return result.render() if result.entries else "No entries."

        return f"Unknown subcommand '{subcmd}'. Use generate/show."

    registry.register_async("codeowners", "Generate CODEOWNERS from git blame", codeowners_handler)

    # ------------------------------------------------------------------
    # /ownership-analyze — Analyze code ownership
    # ------------------------------------------------------------------
    async def ownership_analyze_handler(args: str) -> str:
        """
        Usage: /ownership-analyze [path]
               /ownership-analyze bus-factor [path]
               /ownership-analyze silos [path]
               /ownership-analyze orphaned [path]
        """
        from lidco.ownership.analyzer import OwnershipAnalyzer
        from lidco.ownership.generator import CodeownersGenerator

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "summary"
        repo_path = parts[1] if len(parts) > 1 else (
            parts[0] if parts and parts[0] not in ("summary", "bus-factor", "silos", "orphaned") else "."
        )

        gen = CodeownersGenerator()
        co_result = gen.generate_from_git(repo_path)
        blame_entries = []
        for entry in co_result.entries:
            pass  # We need raw blame; re-fetch
        # Re-generate blame data directly
        tracked = gen._list_tracked_files(repo_path)
        for fpath in tracked:
            blame_entries.extend(gen._blame_file(repo_path, fpath))

        analyzer = OwnershipAnalyzer()
        report = analyzer.analyze(blame_entries, tracked_files=tracked)

        if subcmd == "summary" or (parts and parts[0] not in ("summary", "bus-factor", "silos", "orphaned")):
            s = report.summary()
            return (
                f"Ownership Analysis:\n"
                f"  Overall bus factor: {s['overall_bus_factor']}\n"
                f"  Knowledge silos: {s['silo_count']}\n"
                f"  Orphaned files: {s['orphaned_count']}\n"
                f"  Coverage gaps: {s['gap_count']}\n"
                f"  Directories analyzed: {s['directory_count']}"
            )

        if subcmd == "bus-factor":
            if not report.bus_factors:
                return "No bus factor data."
            lines = [f"Bus Factor Analysis ({len(report.bus_factors)} dirs):"]
            for bf in report.bus_factors[:20]:
                contribs = ", ".join(f"{a}({l})" for a, l in bf.top_contributors[:3])
                lines.append(f"  {bf.path}: factor={bf.bus_factor} [{contribs}]")
            return "\n".join(lines)

        if subcmd == "silos":
            if not report.knowledge_silos:
                return "No knowledge silos detected."
            lines = [f"Knowledge Silos ({len(report.knowledge_silos)}):"]
            for silo in report.knowledge_silos:
                lines.append(
                    f"  {silo.path}: {silo.sole_owner} "
                    f"({silo.ownership_fraction:.0%}, {silo.total_lines} lines)"
                )
            return "\n".join(lines)

        if subcmd == "orphaned":
            if not report.orphaned_files:
                return "No orphaned files."
            lines = [f"Orphaned Files ({len(report.orphaned_files)}):"]
            for o in report.orphaned_files[:30]:
                lines.append(f"  {o.file_path}: {o.reason}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use summary/bus-factor/silos/orphaned."

    registry.register_async("ownership-analyze", "Analyze code ownership distribution", ownership_analyze_handler)

    # ------------------------------------------------------------------
    # /review-route — Route reviews to owners
    # ------------------------------------------------------------------
    async def review_route_handler(args: str) -> str:
        """
        Usage: /review-route <file1> [file2] ...
               /review-route round-robin <team> [count]
               /review-route least-loaded <team>
        """
        from lidco.ownership.review_router import ReviewRouter, Reviewer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /review-route <file1> [file2] ...\n"
                "       /review-route round-robin <team> [count]\n"
                "       /review-route least-loaded <team>"
            )

        subcmd = parts[0].lower()
        router = ReviewRouter()

        if subcmd == "round-robin":
            team = parts[1] if len(parts) > 1 else "default"
            count = int(parts[2]) if len(parts) > 2 else 1
            picked = router.route_round_robin(team, count)
            if not picked:
                return f"No available reviewers in team '{team}'."
            return f"Round-robin reviewers: {', '.join(picked)}"

        if subcmd == "least-loaded":
            team = parts[1] if len(parts) > 1 else "default"
            reviewer = router.find_least_loaded(team)
            if not reviewer:
                return f"No available reviewers in team '{team}'."
            return f"Least loaded reviewer: {reviewer}"

        # Default: route changed files
        result = router.route(parts)
        s = result.summary()
        lines = [f"Review Routing ({s['assigned_count']} assigned, {s['unassigned_count']} unassigned):"]
        for a in result.assignments:
            lines.append(f"  {a.file_pattern} -> {', '.join(a.reviewers)} ({a.reason})")
        if result.unassigned:
            lines.append(f"  Unassigned: {', '.join(result.unassigned)}")
        return "\n".join(lines)

    registry.register_async("review-route", "Route reviews to code owners", review_route_handler)

    # ------------------------------------------------------------------
    # /knowledge-transfer — Plan knowledge transfer
    # ------------------------------------------------------------------
    async def knowledge_transfer_handler(args: str) -> str:
        """
        Usage: /knowledge-transfer [path]
               /knowledge-transfer critical [path]
               /knowledge-transfer pairings [path]
               /knowledge-transfer doc-gaps [path]
        """
        from lidco.ownership.analyzer import OwnershipAnalyzer
        from lidco.ownership.generator import CodeownersGenerator
        from lidco.ownership.transfer import KnowledgeTransferPlanner

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0].lower() if parts else "summary"
        repo_path = parts[1] if len(parts) > 1 else (
            parts[0] if parts and parts[0] not in ("summary", "critical", "pairings", "doc-gaps") else "."
        )

        gen = CodeownersGenerator()
        tracked = gen._list_tracked_files(repo_path)
        blame_entries = []
        for fpath in tracked:
            blame_entries.extend(gen._blame_file(repo_path, fpath))

        analyzer = OwnershipAnalyzer()
        report = analyzer.analyze(blame_entries, tracked_files=tracked)

        planner = KnowledgeTransferPlanner()
        plan = planner.plan(report)

        if subcmd == "summary" or (parts and parts[0] not in ("summary", "critical", "pairings", "doc-gaps")):
            s = plan.summary()
            return (
                f"Knowledge Transfer Plan:\n"
                f"  Critical paths: {s['critical_path_count']}\n"
                f"  Pairing suggestions: {s['pairing_suggestion_count']}\n"
                f"  Doc gaps: {s['doc_gap_count']}"
            )

        if subcmd == "critical":
            if not plan.critical_paths:
                return "No critical paths identified."
            lines = [f"Critical Paths ({len(plan.critical_paths)}):"]
            for cp in plan.critical_paths:
                lines.append(
                    f"  {cp.path}: owner={cp.sole_owner}, "
                    f"risk={cp.risk_score:.2f}, {cp.total_lines} lines"
                )
            return "\n".join(lines)

        if subcmd == "pairings":
            if not plan.pairing_suggestions:
                return "No pairing suggestions."
            lines = [f"Pairing Suggestions ({len(plan.pairing_suggestions)}):"]
            for ps in plan.pairing_suggestions:
                lines.append(f"  {ps.expert} + {ps.learner} on {ps.path} ({ps.reason})")
            return "\n".join(lines)

        if subcmd == "doc-gaps":
            if not plan.doc_gaps:
                return "No documentation gaps."
            lines = [f"Doc Gaps ({len(plan.doc_gaps)}):"]
            for dg in plan.doc_gaps:
                lines.append(f"  {dg.directory}: {dg.file_count} files, readme={dg.has_readme}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use summary/critical/pairings/doc-gaps."

    registry.register_async("knowledge-transfer", "Plan knowledge transfer", knowledge_transfer_handler)
