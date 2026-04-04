"""Q301 CLI commands — /conflict-detect, /conflict-resolve, /merge-strategy, /verify-merge

Registered via register_q301_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q301_commands(registry) -> None:
    """Register Q301 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /conflict-detect [files_a] [files_b]
    # ------------------------------------------------------------------
    async def conflict_detect_handler(args: str) -> str:
        from lidco.merge.detector import ConflictDetector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /conflict-detect <files_a_csv> <files_b_csv>\n"
                "  Predict which files may conflict between two file lists."
            )

        files_a = parts[0].split(",") if len(parts) > 0 else []
        files_b = parts[1].split(",") if len(parts) > 1 else []

        detector = ConflictDetector()
        affected = detector.predict_affected(files_a, files_b)

        if not affected:
            return "No overlapping files detected — merge should be clean."
        return f"Potentially conflicting files ({len(affected)}):\n" + "\n".join(
            f"  {f}" for f in affected
        )

    # ------------------------------------------------------------------
    # /conflict-resolve <strategy>
    # ------------------------------------------------------------------
    async def conflict_resolve_handler(args: str) -> str:
        from lidco.merge.detector import Conflict
        from lidco.merge.resolver import ConflictResolver

        parts = shlex.split(args) if args.strip() else []
        strategy = parts[0] if parts else "smart"

        if strategy == "help":
            return (
                "Usage: /conflict-resolve [strategy]\n"
                "Strategies: ours, theirs, union, smart (default)"
            )

        # Demo conflict for illustration
        conflict = Conflict(
            file_path="example.py",
            line_start=10,
            line_end=15,
            text_a="def foo():\n    return 1\n",
            text_b="def foo():\n    return 2\n",
        )

        resolver = ConflictResolver()
        resolution = resolver.resolve(conflict, strategy=strategy)
        return (
            f"Strategy: {resolution.strategy}\n"
            f"Confidence: {resolution.confidence:.0%}\n"
            f"Explanation: {resolution.explanation}\n"
            f"Result:\n{resolution.resolved_text}"
        )

    # ------------------------------------------------------------------
    # /merge-strategy [recommend | compare | pros-cons <strategy>]
    # ------------------------------------------------------------------
    async def merge_strategy_handler(args: str) -> str:
        from lidco.merge.strategy import BranchInfo, MergeStrategy

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "recommend"

        ms = MergeStrategy()

        if subcmd == "recommend":
            count = int(parts[1]) if len(parts) > 1 else 5
            branch = BranchInfo(name="feature", commit_count=count)
            rec = ms.recommend(branch)
            return f"Recommended strategy for {count} commits: {rec}"

        if subcmd == "compare":
            comparison = ms.compare_strategies()
            lines = []
            for name, pc in comparison.items():
                lines.append(f"[{name}]")
                for p in pc["pros"]:
                    lines.append(f"  + {p}")
                for c in pc["cons"]:
                    lines.append(f"  - {c}")
            return "\n".join(lines)

        if subcmd == "pros-cons":
            strat = parts[1] if len(parts) > 1 else "merge"
            try:
                pc = ms.pros_cons(strat)
            except ValueError as exc:
                return str(exc)
            lines = [f"Strategy: {strat}"]
            for p in pc["pros"]:
                lines.append(f"  + {p}")
            for c in pc["cons"]:
                lines.append(f"  - {c}")
            return "\n".join(lines)

        return (
            "Usage: /merge-strategy <subcommand>\n"
            "  recommend [commits]    recommend strategy\n"
            "  compare                compare all strategies\n"
            "  pros-cons <strategy>   show pros/cons"
        )

    # ------------------------------------------------------------------
    # /verify-merge [check | report]
    # ------------------------------------------------------------------
    async def verify_merge_handler(args: str) -> str:
        from lidco.merge.verifier import PostMergeVerifier, VerifyResult

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "report"

        verifier = PostMergeVerifier()

        if subcmd == "check":
            # Demo: check empty merge
            result = verifier.verify({}, {})
            return f"Verification: {'PASS' if result.passed else 'FAIL'} ({result.total_issues} issues)"

        if subcmd == "report":
            result = verifier.verify(
                {"a.py": "print(1)\n"},
                {"a.py": "print(1)\n", "b.py": "new\n"},
            )
            return verifier.report(result, regressions=[])

        return (
            "Usage: /verify-merge <subcommand>\n"
            "  check    quick pass/fail check\n"
            "  report   full verification report"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(
        SlashCommand("conflict-detect", "Predict merge conflicts", conflict_detect_handler)
    )
    registry.register(
        SlashCommand("conflict-resolve", "Resolve merge conflicts", conflict_resolve_handler)
    )
    registry.register(
        SlashCommand("merge-strategy", "Merge strategy advisor", merge_strategy_handler)
    )
    registry.register(
        SlashCommand("verify-merge", "Post-merge verification", verify_merge_handler)
    )
