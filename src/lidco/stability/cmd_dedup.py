"""
Slash Command Registry Deduplication Validator.

Detects duplicate command registrations, shadow chains, and suggests fixes.
"""
from __future__ import annotations


class CommandDedupValidator:
    """Validates slash command registrations for duplicates and shadowing."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_duplicates(self, commands: list[dict]) -> list[dict]:
        """Find duplicate command registrations.

        Args:
            commands: List of dicts with "name", "description", "line" keys.

        Returns:
            List of dicts with "name", "registrations" (list of line numbers),
            "winner" (last registration line).
        """
        # Group by name
        groups: dict[str, list[dict]] = {}
        for cmd in commands:
            name = cmd["name"]
            groups.setdefault(name, []).append(cmd)

        duplicates: list[dict] = []
        for name, registrations in groups.items():
            if len(registrations) < 2:
                continue
            lines = [r["line"] for r in registrations]
            winner = max(lines)
            duplicates.append(
                {
                    "name": name,
                    "registrations": lines,
                    "winner": winner,
                }
            )
        return duplicates

    def analyze_shadows(self, commands: list[dict]) -> list[dict]:
        """Find commands that shadow earlier registrations.

        A command shadows another when a later registration of the same name
        overrides an earlier one.

        Args:
            commands: List of dicts with "name", "description", "line" keys.

        Returns:
            List of dicts with "shadowed_name", "original_line", "shadow_line",
            "description".
        """
        # Track first-seen registration per name
        first_seen: dict[str, dict] = {}
        shadows: list[dict] = []

        for cmd in commands:
            name = cmd["name"]
            if name not in first_seen:
                first_seen[name] = cmd
            else:
                original = first_seen[name]
                shadows.append(
                    {
                        "shadowed_name": name,
                        "original_line": original["line"],
                        "shadow_line": cmd["line"],
                        "description": cmd.get("description", ""),
                    }
                )
                # Update so next shadow points to current, not original
                first_seen[name] = cmd

        return shadows

    def track_override_chain(self, commands: list[dict]) -> dict:
        """Build override chain map.

        Args:
            commands: List of dicts with "name", "description", "line" keys.

        Returns:
            Dict mapping name -> list of registration dicts in order.
        """
        chain: dict[str, list[dict]] = {}
        for cmd in commands:
            name = cmd["name"]
            chain.setdefault(name, []).append(cmd)
        return chain

    def suggest_fixes(self, duplicates: list[dict]) -> list[str]:
        """Generate dedup fix suggestions.

        Args:
            duplicates: Output of find_duplicates().

        Returns:
            List of human-readable suggestion strings.
        """
        suggestions: list[str] = []
        for dup in duplicates:
            name = dup["name"]
            registrations = dup["registrations"]
            winner = dup["winner"]
            losers = [ln for ln in registrations if ln != winner]
            loser_str = ", ".join(f"line {ln}" for ln in sorted(losers))
            suggestions.append(
                f"Command '{name}' is registered {len(registrations)} times. "
                f"Remove duplicate registrations at {loser_str}; "
                f"keep the registration at line {winner} (active winner)."
            )
        return suggestions
