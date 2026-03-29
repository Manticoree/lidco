"""BugBotPRPoster — post fix proposals as inline PR comments (Task 699)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lidco.review.bugbot_pr_trigger import BugSeverity, _SEVERITY_ORDER
from lidco.review.bugbot_fix_agent import BugBotFixProposal


@dataclass
class PostResult:
    posted: int
    skipped: int
    errors: list[str]
    comment_ids: list[str]


class BugBotPRPoster:
    """Post BugBot fix proposals as inline PR comments."""

    def __init__(self, gh_poster=None):
        self._gh_poster = gh_poster
        self._posted_ids: set[str] = set()

    def post(
        self,
        proposals: list[BugBotFixProposal],
        pr_number: int,
        dry_run: bool = False,
    ) -> PostResult:
        """Post proposals as inline PR comments."""
        posted = 0
        skipped = 0
        errors: list[str] = []
        comment_ids: list[str] = []

        # Sort by severity (CRITICAL first)
        sorted_proposals = sorted(
            proposals,
            key=lambda p: _SEVERITY_ORDER.get(p.finding.severity, 99),
        )

        for proposal in sorted_proposals:
            # Skip if: empty patch AND confidence < 0.3
            if not proposal.patch and proposal.confidence < 0.3:
                skipped += 1
                continue

            # Duplicate detection
            dup_key = self._dedup_key(proposal)
            if dup_key in self._posted_ids:
                skipped += 1
                continue

            if dry_run:
                self._posted_ids.add(dup_key)
                posted += 1
                comment_ids.append(f"dry-run-{posted}")
                continue

            if self._gh_poster is None:
                skipped += 1
                errors.append(f"No gh_poster configured for {proposal.finding.file}:{proposal.finding.line}")
                continue

            body = self.format_comment(proposal)
            try:
                cid = self._gh_poster.post_comment(
                    pr_number,
                    proposal.finding.file,
                    proposal.finding.line,
                    body,
                )
                self._posted_ids.add(dup_key)
                posted += 1
                comment_ids.append(str(cid))
            except Exception as exc:
                errors.append(f"Failed to post for {proposal.finding.file}:{proposal.finding.line}: {exc}")

        return PostResult(posted=posted, skipped=skipped, errors=errors, comment_ids=comment_ids)

    def format_comment(self, proposal: BugBotFixProposal) -> str:
        """Format a proposal as a markdown comment body."""
        f = proposal.finding
        severity_label = f.severity.value.upper()
        lines = [
            f"**BugBot** [{severity_label}] `{f.rule_id}`",
            "",
            f"> {f.message}",
            "",
            f"**Rationale:** {proposal.rationale}",
        ]
        if proposal.patch:
            lines.append("")
            lines.append("```diff")
            lines.append(proposal.patch)
            lines.append("```")
        if proposal.confidence > 0:
            lines.append("")
            lines.append(f"Confidence: {proposal.confidence:.0%}")
        return "\n".join(lines)

    def clear_posted(self) -> None:
        """Reset duplicate tracking."""
        self._posted_ids.clear()

    @staticmethod
    def _dedup_key(proposal: BugBotFixProposal) -> str:
        f = proposal.finding
        return f"{f.file}:{f.line}:{f.rule_id}"
