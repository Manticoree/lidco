"""Smell dashboard — aggregate and display smell metrics."""

from __future__ import annotations

from lidco.smells.scanner import SmellMatch


class SmellDashboard:
    """Aggregated view of smell scan results."""

    def __init__(self, matches: list[SmellMatch]) -> None:
        self._matches = list(matches)

    # -- aggregations -------------------------------------------------------

    def by_severity(self) -> dict[str, int]:
        """Count matches grouped by severity."""
        counts: dict[str, int] = {}
        for m in self._matches:
            counts[m.severity] = counts.get(m.severity, 0) + 1
        return counts

    def by_file(self) -> dict[str, int]:
        """Count matches grouped by file."""
        counts: dict[str, int] = {}
        for m in self._matches:
            counts[m.file] = counts.get(m.file, 0) + 1
        return counts

    def worst_files(self, limit: int = 10) -> list[tuple[str, int]]:
        """Return top *limit* files sorted by smell count descending."""
        file_counts = self.by_file()
        ranked = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]

    def improvement_score(self) -> float:
        """Return a 0–100 score (higher = fewer smells).

        Score is computed as: max(0, 100 - total_smells * severity_weight).
        Critical = 10, high = 5, medium = 2, low = 1.
        """
        weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
        penalty = 0.0
        for m in self._matches:
            penalty += weights.get(m.severity, 1)
        return max(0.0, min(100.0, 100.0 - penalty))

    def render(self) -> str:
        """Render a text dashboard."""
        lines: list[str] = []
        lines.append("=== Code Smell Dashboard ===")
        lines.append("")

        total = len(self._matches)
        lines.append(f"Total smells: {total}")
        lines.append(f"Improvement score: {self.improvement_score():.1f}/100")
        lines.append("")

        # By severity
        lines.append("By severity:")
        sev = self.by_severity()
        for s in ("critical", "high", "medium", "low"):
            count = sev.get(s, 0)
            if count:
                lines.append(f"  {s}: {count}")

        # Worst files
        worst = self.worst_files(5)
        if worst:
            lines.append("")
            lines.append("Worst files:")
            for fname, count in worst:
                display = fname if fname else "<unnamed>"
                lines.append(f"  {display}: {count} smell(s)")

        return "\n".join(lines)
