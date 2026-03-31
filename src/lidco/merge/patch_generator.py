"""Patch generator — unified diff generation, parsing, and application (stdlib only)."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass
class PatchFile:
    """Parsed representation of a single file's patch."""

    file_path: str
    old_content: str
    new_content: str
    hunks: list[str] = field(default_factory=list)


class PatchGenerator:
    """Generate, parse, apply, and reverse unified diff patches."""

    def generate(
        self,
        file_path: str,
        old: str,
        new: str,
        context_lines: int = 3,
    ) -> str:
        """Generate a unified diff patch for a single file."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        # Ensure final newline for clean diffs
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=context_lines,
        )
        return "".join(diff)

    def generate_multi(self, files: list[tuple[str, str, str]]) -> str:
        """Generate a multi-file patch. Each tuple is (path, old, new)."""
        patches: list[str] = []
        for path, old, new in files:
            p = self.generate(path, old, new)
            if p:
                patches.append(p)
        return "\n".join(patches)

    def parse_patch(self, patch: str) -> list[PatchFile]:
        """Parse a unified diff patch back to ``PatchFile`` objects."""
        results: list[PatchFile] = []
        current_path = ""
        current_hunks: list[str] = []
        current_old_lines: list[str] = []
        current_new_lines: list[str] = []
        in_hunk = False

        lines = patch.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect --- a/path
            if line.startswith("--- a/"):
                # Save previous file if any
                if current_path:
                    results.append(
                        PatchFile(
                            file_path=current_path,
                            old_content="".join(current_old_lines),
                            new_content="".join(current_new_lines),
                            hunks=current_hunks,
                        )
                    )
                # Extract path from +++ line
                i += 1
                if i < len(lines) and lines[i].startswith("+++ b/"):
                    current_path = lines[i][6:].strip()
                else:
                    current_path = line[6:].strip()
                current_hunks = []
                current_old_lines = []
                current_new_lines = []
                in_hunk = False
                i += 1
                continue

            # Hunk header
            if line.startswith("@@"):
                in_hunk = True
                current_hunks.append(line.rstrip("\n"))
                i += 1
                continue

            if in_hunk:
                if line.startswith("-"):
                    current_old_lines.append(line[1:])
                elif line.startswith("+"):
                    current_new_lines.append(line[1:])
                elif line.startswith(" "):
                    current_old_lines.append(line[1:])
                    current_new_lines.append(line[1:])

            i += 1

        # Save last file
        if current_path:
            results.append(
                PatchFile(
                    file_path=current_path,
                    old_content="".join(current_old_lines),
                    new_content="".join(current_new_lines),
                    hunks=current_hunks,
                )
            )

        return results

    def apply(self, original: str, patch: str) -> str:
        """Apply a unified diff patch to original content.

        This is a simplified apply that works by parsing the patch
        and returning the new content from the diff.
        """
        old_lines = original.splitlines(keepends=True)
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"

        new_lines: list[str] = []
        patch_lines = patch.splitlines(keepends=True)

        hunks = self._parse_hunks(patch_lines)
        if not hunks:
            return original

        old_idx = 0
        for hunk_start, hunk_ops in hunks:
            # Copy lines before this hunk
            while old_idx < hunk_start:
                if old_idx < len(old_lines):
                    new_lines.append(old_lines[old_idx])
                old_idx += 1

            # Apply hunk operations
            for op, text in hunk_ops:
                if op == " ":
                    new_lines.append(text)
                    old_idx += 1
                elif op == "-":
                    old_idx += 1
                elif op == "+":
                    new_lines.append(text)

        # Copy remaining lines
        while old_idx < len(old_lines):
            new_lines.append(old_lines[old_idx])
            old_idx += 1

        result = "".join(new_lines)
        # Strip trailing newline if original didn't have one
        if not original.endswith("\n") and result.endswith("\n"):
            result = result[:-1]
        return result

    def reverse(self, patch: str) -> str:
        """Generate a reverse patch (swap old/new)."""
        lines = patch.splitlines(keepends=True)
        reversed_lines: list[str] = []

        for line in lines:
            if line.startswith("--- a/"):
                path = line[6:]
                reversed_lines.append(f"+++ b/{path}")
            elif line.startswith("+++ b/"):
                path = line[6:]
                reversed_lines.append(f"--- a/{path}")
            elif line.startswith("@@"):
                # Swap the old/new ranges in the hunk header
                reversed_lines.append(self._reverse_hunk_header(line))
            elif line.startswith("-"):
                reversed_lines.append("+" + line[1:])
            elif line.startswith("+"):
                reversed_lines.append("-" + line[1:])
            else:
                reversed_lines.append(line)

        return "".join(reversed_lines)

    def _parse_hunks(
        self, patch_lines: list[str]
    ) -> list[tuple[int, list[tuple[str, str]]]]:
        """Parse hunks from patch lines into (start_line, operations)."""
        hunks: list[tuple[int, list[tuple[str, str]]]] = []
        current_ops: list[tuple[str, str]] = []
        hunk_start = 0

        for line in patch_lines:
            stripped = line.rstrip("\n")
            if stripped.startswith("@@"):
                if current_ops:
                    hunks.append((hunk_start, current_ops))
                    current_ops = []
                # Parse @@ -old_start,old_count +new_start,new_count @@
                m = re.match(r"@@ -(\d+)", stripped)
                hunk_start = int(m.group(1)) - 1 if m else 0
            elif stripped.startswith("---") or stripped.startswith("+++"):
                continue
            elif stripped.startswith("-"):
                current_ops.append(("-", line[1:]))
            elif stripped.startswith("+"):
                current_ops.append(("+", line[1:]))
            elif stripped.startswith(" "):
                current_ops.append((" ", line[1:]))

        if current_ops:
            hunks.append((hunk_start, current_ops))

        return hunks

    def _reverse_hunk_header(self, header: str) -> str:
        """Reverse a @@ hunk header by swapping old/new ranges."""
        m = re.match(
            r"(@@ -)(\d+(?:,\d+)?)( \+)(\d+(?:,\d+)?)( @@.*)", header.rstrip("\n")
        )
        if not m:
            return header
        result = f"@@ -{m.group(4)} +{m.group(2)} @@{m.group(5)[3:]}\n"
        return result
