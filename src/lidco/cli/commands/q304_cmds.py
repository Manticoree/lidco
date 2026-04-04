"""Q304 CLI commands — /bump-version, /changelog, /release-notes, /tag

Registered via register_q304_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q304_commands(registry) -> None:
    """Register Q304 slash commands onto the given registry."""

    # ------------------------------------------------------------------ #
    # /bump-version — Semantic version bumping                             #
    # ------------------------------------------------------------------ #
    async def bump_version_handler(args: str) -> str:
        """
        Usage: /bump-version <version> <major|minor|patch>
               /bump-version auto <version> <commit1> [commit2 ...]
        """
        from lidco.release.bumper import VersionBumper

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /bump-version <subcommand>\n"
                "  <version> major          bump major version\n"
                "  <version> minor          bump minor version\n"
                "  <version> patch          bump patch version\n"
                "  auto <version> <commits> detect bump type from commits"
            )

        bumper = VersionBumper()

        if parts[0].lower() == "auto":
            if len(parts) < 3:
                return "Error: Usage: /bump-version auto <version> <commit1> [commit2 ...]"
            version = parts[1]
            commits = parts[2:]
            try:
                new_version = bumper.from_commits(commits, version)
                bump_type = bumper.detect_bump_type(commits)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Detected bump: {bump_type}\n{version} -> {new_version}"

        if len(parts) < 2:
            return "Error: Usage: /bump-version <version> <major|minor|patch>"

        version = parts[0]
        bump_type = parts[1].lower()

        try:
            if bump_type == "major":
                result = bumper.bump_major(version)
            elif bump_type == "minor":
                result = bumper.bump_minor(version)
            elif bump_type == "patch":
                result = bumper.bump_patch(version)
            else:
                return f"Unknown bump type '{bump_type}'. Use major/minor/patch."
        except ValueError as exc:
            return f"Error: {exc}"

        return f"{version} -> {result}"

    registry.register_async("bump-version", "Bump semantic version", bump_version_handler)

    # ------------------------------------------------------------------ #
    # /changelog — Generate changelogs                                     #
    # ------------------------------------------------------------------ #
    _changelog_state: dict[str, object] = {}

    async def changelog_handler(args: str) -> str:
        """
        Usage: /changelog add <type> <message> [--pr <url>]
               /changelog generate <version>
               /changelog keep-a-changelog <version> [--date <YYYY-MM-DD>]
               /changelog clear
        """
        from lidco.release.changelog import ChangelogGenerator2

        if "gen" not in _changelog_state:
            _changelog_state["gen"] = ChangelogGenerator2()

        gen: ChangelogGenerator2 = _changelog_state["gen"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []

        if not parts:
            return (
                "Usage: /changelog <subcommand>\n"
                "  add <type> <message> [--pr <url>]  add an entry\n"
                "  generate <version>                 render simple changelog\n"
                "  keep-a-changelog <version> [--date YYYY-MM-DD]\n"
                "  clear                              clear all entries"
            )

        subcmd = parts[0].lower()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /changelog add <type> <message> [--pr <url>]"
            entry_type = parts[1]
            message = parts[2]
            pr_url = ""
            i = 3
            while i < len(parts):
                if parts[i] == "--pr" and i + 1 < len(parts):
                    i += 1
                    pr_url = parts[i]
                i += 1
            gen.add_entry(entry_type, message, pr_url)
            return f"Added {entry_type} entry: {message}"

        if subcmd == "generate":
            if len(parts) < 2:
                return "Error: version required. Usage: /changelog generate <version>"
            return gen.generate(parts[1])

        if subcmd == "keep-a-changelog":
            if len(parts) < 2:
                return "Error: version required."
            version = parts[1]
            release_date = None
            i = 2
            while i < len(parts):
                if parts[i] == "--date" and i + 1 < len(parts):
                    i += 1
                    release_date = parts[i]
                i += 1
            return gen.keep_a_changelog_format(version, release_date)

        if subcmd == "clear":
            _changelog_state["gen"] = ChangelogGenerator2()
            return "Changelog entries cleared."

        return f"Unknown subcommand '{subcmd}'. Use add/generate/keep-a-changelog/clear."

    registry.register_async("changelog", "Generate changelogs", changelog_handler)

    # ------------------------------------------------------------------ #
    # /release-notes — Generate release notes                              #
    # ------------------------------------------------------------------ #
    async def release_notes_handler(args: str) -> str:
        """
        Usage: /release-notes <version>
        Generates release notes from current changelog entries.
        """
        from lidco.release.changelog import ChangelogGenerator2
        from lidco.release.notes import ReleaseEntry, ReleaseNotesGenerator

        if "gen" not in _changelog_state:
            _changelog_state["gen"] = ChangelogGenerator2()

        gen: ChangelogGenerator2 = _changelog_state["gen"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []

        if not parts:
            return (
                "Usage: /release-notes <version>\n"
                "  Generates release notes from accumulated changelog entries."
            )

        version = parts[0]
        entries = [
            ReleaseEntry(type=e.type, message=e.message)
            for e in gen.entries
        ]

        rng = ReleaseNotesGenerator()
        return rng.generate(version, entries)

    registry.register_async("release-notes", "Generate release notes", release_notes_handler)

    # ------------------------------------------------------------------ #
    # /tag — Manage tags                                                   #
    # ------------------------------------------------------------------ #
    _tag_state: dict[str, object] = {}

    async def tag_handler(args: str) -> str:
        """
        Usage: /tag create <name> [message]
               /tag annotated <name> <message>
               /tag list
               /tag delete <name>
               /tag latest
               /tag find <pattern>
        """
        from lidco.release.tags import TagManager

        if "mgr" not in _tag_state:
            _tag_state["mgr"] = TagManager()

        mgr: TagManager = _tag_state["mgr"]  # type: ignore[assignment]
        parts = shlex.split(args) if args.strip() else []

        if not parts:
            return (
                "Usage: /tag <subcommand>\n"
                "  create <name> [message]      create lightweight tag\n"
                "  annotated <name> <message>   create annotated tag\n"
                "  list                         list all tags\n"
                "  delete <name>                delete a tag\n"
                "  latest                       show latest tag\n"
                "  find <pattern>               find tags matching pattern"
            )

        subcmd = parts[0].lower()

        if subcmd == "create":
            if len(parts) < 2:
                return "Error: tag name required."
            name = parts[1]
            message = parts[2] if len(parts) > 2 else ""
            try:
                tag = mgr.create_tag(name, message)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Tag '{tag.name}' created."

        if subcmd == "annotated":
            if len(parts) < 3:
                return "Error: Usage: /tag annotated <name> <message>"
            try:
                tag = mgr.annotated(parts[1], parts[2])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Annotated tag '{tag.name}' created: {tag.message}"

        if subcmd == "list":
            tags = mgr.list_tags()
            if not tags:
                return "No tags."
            lines = []
            for t in tags:
                kind = "annotated" if t.annotated else "lightweight"
                lines.append(f"  {t.name}  [{kind}]  {t.message or '(no message)'}")
            return "Tags:\n" + "\n".join(lines)

        if subcmd == "delete":
            if len(parts) < 2:
                return "Error: tag name required."
            deleted = mgr.delete_tag(parts[1])
            return f"Tag '{parts[1]}' deleted." if deleted else f"Tag '{parts[1]}' not found."

        if subcmd == "latest":
            tag = mgr.latest()
            if tag is None:
                return "No tags."
            return f"Latest tag: {tag.name} ({tag.message or 'no message'})"

        if subcmd == "find":
            if len(parts) < 2:
                return "Error: pattern required."
            matches = mgr.tags_for_version(parts[1])
            if not matches:
                return f"No tags matching '{parts[1]}'."
            return "Matching tags:\n" + "\n".join(f"  {t.name}" for t in matches)

        return f"Unknown subcommand '{subcmd}'. Use create/annotated/list/delete/latest/find."

    registry.register_async("tag", "Manage release tags", tag_handler)
