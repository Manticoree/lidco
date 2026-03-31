"""Q132 CLI commands: /fs."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q132 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def fs_handler(args: str) -> str:
        from lidco.fs.file_classifier import FileClassifier
        from lidco.fs.directory_walker import DirectoryWalker
        from lidco.fs.duplicate_finder import DuplicateFinder
        from lidco.fs.ignore_rules import IgnoreRules

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "classify":
            if not rest:
                return "Usage: /fs classify <json_paths>"
            try:
                paths = json.loads(rest)
            except json.JSONDecodeError:
                return "Invalid JSON paths."
            classifier = FileClassifier()
            results = classifier.classify_many(paths)
            lines = ["File classifications:"]
            for fc in results:
                lines.append(f"  {fc.path}: {fc.category} / {fc.language}")
            stats = classifier.language_stats(results)
            lines.append("Language stats: " + json.dumps(stats))
            return "\n".join(lines)

        if sub == "walk":
            if not rest:
                return "Usage: /fs walk <root_path>"
            walker = DirectoryWalker()
            try:
                entries = walker.walk(rest)
            except Exception as exc:
                return f"Walk error: {exc}"
            files = walker.files_only(entries)
            dirs = walker.dirs_only(entries)
            total = walker.total_size(entries)
            return (
                f"Walk result for {rest!r}:\n"
                f"  Files: {len(files)}, Dirs: {len(dirs)}, "
                f"Total size: {total} bytes"
            )

        if sub == "dupes":
            if not rest:
                return "Usage: /fs dupes <json_dict>"
            try:
                files_dict = json.loads(rest)
            except json.JSONDecodeError:
                return "Invalid JSON."
            finder = DuplicateFinder()
            groups = finder.find(files_dict)
            summary = finder.summary(groups)
            lines = [f"Duplicate groups: {summary['groups']}",
                     f"Wasted bytes: {summary['total_wasted_bytes']}"]
            for g in groups:
                lines.append(f"  Hash {g.content_hash[:8]}: {g.paths}")
            return "\n".join(lines)

        if sub == "ignore":
            if not rest:
                return "Usage: /fs ignore <gitignore_content> <json_paths>"
            rest_parts = rest.split(maxsplit=1)
            if len(rest_parts) < 2:
                return "Usage: /fs ignore <gitignore_content> <json_paths>"
            try:
                paths = json.loads(rest_parts[1])
            except json.JSONDecodeError:
                return "Invalid JSON paths."
            rules = IgnoreRules()
            rules.load_gitignore(rest_parts[0])
            filtered = rules.filter(paths)
            return f"Rules: {len(rules)}, Kept: {len(filtered)} of {len(paths)}\n" + json.dumps(filtered)

        return (
            "Usage: /fs <sub>\n"
            "  classify <json_paths>                    -- classify files\n"
            "  walk <root>                              -- walk directory\n"
            "  dupes <json_dict>                        -- find duplicates\n"
            "  ignore <gitignore_content> <json_paths>  -- apply ignore rules"
        )

    registry.register(SlashCommand("fs", "File system intelligence (Q132)", fs_handler))
