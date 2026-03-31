"""Present side-by-side comparison of exploration variants."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiffSummary:
    variant_id: str
    strategy: str
    lines_added: int
    lines_removed: int
    files_changed: int
    score: float
    status: str


class DiffPresenter:
    def __init__(self) -> None:
        pass

    def summarize_variant(
        self,
        variant_id: str,
        strategy: str,
        diff: str,
        score: float = 0.0,
        status: str = "completed",
    ) -> DiffSummary:
        """Create a summary of a variant's diff."""
        added = 0
        removed = 0
        files: set[str] = set()
        for line in diff.split("\n"):
            if line.startswith("+++ ") or line.startswith("--- "):
                parts = line.split()
                if len(parts) > 1 and parts[1] != "/dev/null":
                    files.add(parts[1])
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        return DiffSummary(
            variant_id=variant_id,
            strategy=strategy,
            lines_added=added,
            lines_removed=removed,
            files_changed=len(files),
            score=score,
            status=status,
        )

    def format_comparison_table(self, summaries: list[DiffSummary]) -> str:
        """Format summaries as a comparison table."""
        if not summaries:
            return "No variants to compare."

        lines = [
            "| # | Strategy | Status | +Lines | -Lines | Files | Score |",
            "|---|----------|--------|--------|--------|-------|-------|",
        ]
        for i, s in enumerate(summaries, 1):
            lines.append(
                f"| {i} | {s.strategy} | {s.status} | +{s.lines_added} | -{s.lines_removed} | {s.files_changed} | {s.score:.2f} |"
            )
        return "\n".join(lines)

    def format_diff_comparison(
        self,
        diff_a: str,
        diff_b: str,
        label_a: str = "A",
        label_b: str = "B",
    ) -> str:
        """Format two diffs side by side (simplified: sequential with labels)."""
        sections = []
        sections.append(f"=== Variant {label_a} ===")
        sections.append(diff_a if diff_a else "(no changes)")
        sections.append("")
        sections.append(f"=== Variant {label_b} ===")
        sections.append(diff_b if diff_b else "(no changes)")
        return "\n".join(sections)

    def format_winner_announcement(self, summary: DiffSummary) -> str:
        """Format the winner announcement."""
        return (
            f"Winner: Variant {summary.variant_id} ({summary.strategy})\n"
            f"Score: {summary.score:.2f}\n"
            f"Changes: +{summary.lines_added}/-{summary.lines_removed} lines across {summary.files_changed} files"
        )
