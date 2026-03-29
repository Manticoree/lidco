"""BugBotFixAgent — generate fix proposals for BugBot findings (Task 698)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lidco.review.bugbot_pr_trigger import BugBotFinding, BugSeverity


@dataclass
class BugBotFixProposal:
    finding: BugBotFinding
    patch: str
    rationale: str
    confidence: float  # 0.0-1.0


class BugBotFixAgent:
    """Generate minimal fix proposals for BugBot findings."""

    def __init__(self, llm_fn=None):
        self._llm_fn = llm_fn

    def generate_fix(self, finding: BugBotFinding, source: str) -> BugBotFixProposal:
        """Generate a fix proposal for a single finding."""
        if self._llm_fn is not None:
            return self._llm_fix(finding, source)
        return self._rule_fix(finding, source)

    def generate_fixes(
        self,
        findings: list[BugBotFinding],
        source_map: dict[str, str],
    ) -> list[BugBotFixProposal]:
        """Generate fixes for all findings."""
        proposals: list[BugBotFixProposal] = []
        for finding in findings:
            src = source_map.get(finding.file, "")
            proposal = self.generate_fix(finding, src)
            proposals.append(proposal)
        return proposals

    # ------------------------------------------------------------------
    # Rule-based fixes
    # ------------------------------------------------------------------

    def _rule_fix(self, finding: BugBotFinding, source: str) -> BugBotFixProposal:
        rule = finding.rule_id

        if rule == "bare_except":
            patch = self._make_bare_except_patch(finding, source)
            return BugBotFixProposal(
                finding=finding,
                patch=patch,
                rationale="Replace bare `except:` with `except Exception:` to avoid catching SystemExit/KeyboardInterrupt.",
                confidence=0.9,
            )

        if rule == "eval_usage":
            return BugBotFixProposal(
                finding=finding,
                patch="# TODO: Remove eval() usage — consider ast.literal_eval() or explicit parsing",
                rationale="eval() can execute arbitrary code. Consider safer alternatives.",
                confidence=0.6,
            )

        if rule == "hardcoded_secret":
            return BugBotFixProposal(
                finding=finding,
                patch='# Use: import os; value = os.environ.get("SECRET_KEY", "")',
                rationale="Hardcoded secrets should be replaced with environment variables.",
                confidence=0.7,
            )

        if rule == "todo_fixme":
            return BugBotFixProposal(
                finding=finding,
                patch="",
                rationale="TODO/FIXME comment — no automated fix available.",
                confidence=0.0,
            )

        # Unknown rule — no fix
        return BugBotFixProposal(
            finding=finding,
            patch="",
            rationale=f"No automated fix for rule '{rule}'.",
            confidence=0.0,
        )

    def _make_bare_except_patch(self, finding: BugBotFinding, source: str) -> str:
        lines = source.splitlines()
        line_idx = finding.line - 1
        if 0 <= line_idx < len(lines):
            old_line = lines[line_idx]
            new_line = old_line.replace("except:", "except Exception:")
            return f"--- a/{finding.file}\n+++ b/{finding.file}\n@@ -{finding.line},1 +{finding.line},1 @@\n-{old_line}\n+{new_line}"
        return "except: -> except Exception:"

    # ------------------------------------------------------------------
    # LLM-based fixes
    # ------------------------------------------------------------------

    def _llm_fix(self, finding: BugBotFinding, source: str) -> BugBotFixProposal:
        prompt = (
            f"Generate a minimal fix for this issue:\n"
            f"File: {finding.file}\n"
            f"Line: {finding.line}\n"
            f"Rule: {finding.rule_id}\n"
            f"Message: {finding.message}\n"
            f"Severity: {finding.severity.value}\n\n"
            f"Source code:\n{source}\n\n"
            f"Return ONLY the patch (unified diff format) and a one-line rationale separated by ---."
        )
        try:
            response = self._llm_fn(prompt)
            parts = response.split("---", 1)
            patch = parts[0].strip()
            rationale = parts[1].strip() if len(parts) > 1 else "LLM-generated fix"
            return BugBotFixProposal(
                finding=finding,
                patch=patch,
                rationale=rationale,
                confidence=0.8,
            )
        except Exception as exc:
            return BugBotFixProposal(
                finding=finding,
                patch="",
                rationale=f"LLM fix failed: {exc}",
                confidence=0.0,
            )
