"""
Q299 CLI commands — /smart-commit, /split-commit, /validate-commit, /amend-safe

Registered via register_q299_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q299_commands(registry) -> None:
    """Register Q299 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /smart-commit
    # ------------------------------------------------------------------
    async def smart_commit_handler(args: str) -> str:
        """
        Usage: /smart-commit <unified_diff>
               /smart-commit --classify <diff>
               /smart-commit --scope <diff>
        Analyse staged diff and suggest a commit message.
        """
        from lidco.smartgit.commit_analyzer import CommitAnalyzer

        if not args.strip():
            return (
                "Usage: /smart-commit <unified_diff>\n"
                "  --classify <diff>   show category only\n"
                "  --scope <diff>      show scope only\n"
                "Analyse a diff and suggest a conventional commit message."
            )

        analyzer = CommitAnalyzer()

        if args.strip().startswith("--classify"):
            diff = args.strip()[len("--classify"):].strip()
            if not diff:
                return "Error: diff text required after --classify."
            return analyzer.classify(diff)

        if args.strip().startswith("--scope"):
            diff = args.strip()[len("--scope"):].strip()
            if not diff:
                return "Error: diff text required after --scope."
            scope = analyzer.extract_scope(diff)
            return scope if scope else "(no scope detected)"

        result = analyzer.analyze(args.strip())
        lines = [
            f"Category : {result.category}",
            f"Scope    : {result.scope or '(none)'}",
            f"Files    : {', '.join(result.files) or '(none)'}",
            f"Changes  : +{result.additions}/-{result.deletions}",
            f"Suggested: {result.message}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /split-commit
    # ------------------------------------------------------------------
    async def split_commit_handler(args: str) -> str:
        """
        Usage: /split-commit <unified_diff>
               /split-commit --by-file file1 file2 ...
        Suggest how to split a large changeset.
        """
        from lidco.smartgit.splitter import CommitSplitter

        if not args.strip():
            return (
                "Usage: /split-commit <unified_diff>\n"
                "  --by-file f1 f2 ...  group files by directory\n"
                "Suggest how to split a large changeset into smaller commits."
            )

        splitter = CommitSplitter()

        if args.strip().startswith("--by-file"):
            rest = args.strip()[len("--by-file"):].strip()
            files = shlex.split(rest) if rest else []
            if not files:
                return "Error: provide at least one file path."
            groups = splitter.split_by_file(files)
            lines = []
            for g in groups:
                lines.append(f"[{g.directory}] {', '.join(g.files)}")
            return "\n".join(lines) if lines else "No groups."

        groups = splitter.suggest_splits(args.strip())
        lines = []
        for g in groups:
            lines.append(f"[{g.label}] {', '.join(g.files)} — {g.reason}")
        return "\n".join(lines) if lines else "No split suggestions."

    # ------------------------------------------------------------------
    # /validate-commit
    # ------------------------------------------------------------------
    async def validate_commit_handler(args: str) -> str:
        """
        Usage: /validate-commit <message>
        Validate a commit message against conventional-commit rules.
        """
        from lidco.smartgit.validator import CommitValidator

        if not args.strip():
            return (
                "Usage: /validate-commit <message>\n"
                "Validate a commit message against conventional-commit rules."
            )

        validator = CommitValidator()
        result = validator.validate(args.strip())
        lines = [
            f"Valid        : {'yes' if result.valid else 'no'}",
            f"Conventional : {'yes' if result.is_conventional else 'no'}",
            f"Breaking     : {'yes' if result.has_breaking else 'no'}",
        ]
        if result.issues:
            lines.append("Issues:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /amend-safe
    # ------------------------------------------------------------------
    async def amend_safe_handler(args: str) -> str:
        """
        Usage: /amend-safe fixup <original_hash> <message>
               /amend-safe preserve <hash>
               /amend-safe plan <hash1> <hash2> ...
        Safe amend / fixup utilities.
        """
        from lidco.smartgit.amender import CommitAmender

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /amend-safe <subcommand>\n"
                "  fixup <hash> <message>   create a fixup entry\n"
                "  preserve <hash>          preserve original ref\n"
                "  plan <h1> <h2> ...       show auto-squash plan"
            )

        amender = CommitAmender()
        subcmd = parts[0].lower()

        if subcmd == "fixup":
            if len(parts) < 3:
                return "Error: Usage: /amend-safe fixup <hash> <message>"
            fid = amender.create_fixup(parts[1], " ".join(parts[2:]))
            return f"Fixup created: {fid} for {parts[1]}"

        if subcmd == "preserve":
            if len(parts) < 2:
                return "Error: Usage: /amend-safe preserve <hash>"
            ref = amender.preserve_original(parts[1])
            return f"Preserved {parts[1]} as {ref}"

        if subcmd == "plan":
            if len(parts) < 2:
                return "Error: provide at least one commit hash."
            plan = amender.auto_squash_plan(parts[1:])
            lines = [f"{e.action} {e.commit_hash} {e.message}" for e in plan]
            return "\n".join(lines) if lines else "Empty plan."

        return f"Unknown subcommand: {subcmd}"

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("smart-commit", "Analyze diff and suggest commit message", smart_commit_handler))
    registry.register(SlashCommand("split-commit", "Suggest commit split strategy", split_commit_handler))
    registry.register(SlashCommand("validate-commit", "Validate commit message", validate_commit_handler))
    registry.register(SlashCommand("amend-safe", "Safe amend/fixup utilities", amend_safe_handler))
