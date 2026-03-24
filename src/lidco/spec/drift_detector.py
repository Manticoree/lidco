"""DriftDetector — checks if code still satisfies requirements.md criteria.

Compares acceptance criteria against recent git diff + test results using
heuristic analysis (and optionally LLM confirmation).
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SPEC_DIR = ".lidco/spec"


@dataclass
class DriftReport:
    drifted_criteria: list[str] = field(default_factory=list)
    ok_criteria: list[str] = field(default_factory=list)
    confidence: float = 1.0
    summary: str = ""

    @property
    def has_drift(self) -> bool:
        return len(self.drifted_criteria) > 0

    def to_markdown(self) -> str:
        lines = [
            "# Spec Drift Report",
            "",
            f"**Confidence:** {self.confidence:.0%}",
            f"**Drifted:** {len(self.drifted_criteria)}  |  **OK:** {len(self.ok_criteria)}",
            "",
        ]
        if self.drifted_criteria:
            lines += ["## Drifted Criteria", ""]
            for c in self.drifted_criteria:
                lines.append(f"- [!] {c}")
            lines.append("")
        if self.ok_criteria:
            lines += ["## Satisfied Criteria", ""]
            for c in self.ok_criteria:
                lines.append(f"- [ok] {c}")
            lines.append("")
        if self.summary:
            lines += ["## Summary", "", self.summary, ""]
        return "\n".join(lines)


class DriftDetector:
    """Heuristically checks for spec drift by comparing criteria against code."""

    def __init__(
        self,
        llm_client: Any | None = None,
        git_diff_lines: int = 300,
    ) -> None:
        self._llm = llm_client
        self._git_diff_lines = git_diff_lines

    def check(self, project_dir: Path) -> DriftReport:
        """Run drift check.  Returns DriftReport (empty if no spec)."""
        req_path = Path(project_dir) / _SPEC_DIR / "requirements.md"
        if not req_path.exists():
            return DriftReport(
                ok_criteria=[],
                drifted_criteria=[],
                confidence=1.0,
                summary="No spec found — drift check skipped.",
            )

        criteria = self._extract_criteria(req_path.read_text(encoding="utf-8"))
        if not criteria:
            return DriftReport(confidence=1.0, summary="No acceptance criteria found in spec.")

        recent_diff = self._get_recent_diff(Path(project_dir))
        test_names = self._get_test_names(Path(project_dir))

        if self._llm:
            return self._llm_check(criteria, recent_diff, test_names)
        return self._heuristic_check(criteria, recent_diff, test_names)

    # ------------------------------------------------------------------

    def _extract_criteria(self, requirements_text: str) -> list[str]:
        """Extract 'The system shall...' lines from requirements.md."""
        criteria: list[str] = []
        in_section = False
        for line in requirements_text.splitlines():
            stripped = line.strip()
            if stripped == "## Acceptance Criteria":
                in_section = True
                continue
            if stripped.startswith("## ") and in_section:
                break
            if in_section and stripped:
                # Remove leading "1. " numbering
                text = re.sub(r"^\d+\.\s*", "", stripped)
                if text:
                    criteria.append(text)
        return criteria

    def _get_recent_diff(self, project_dir: Path) -> str:
        """Get recent git diff (last commit + working tree)."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "--", "*.py"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                timeout=10,
            )
            lines = result.stdout.splitlines()[: self._git_diff_lines]
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_test_names(self, project_dir: Path) -> list[str]:
        """Collect test function names as evidence of spec coverage."""
        names: list[str] = []
        tests_dir = project_dir / "tests"
        if not tests_dir.exists():
            return names
        for p in tests_dir.rglob("test_*.py"):
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                names.extend(re.findall(r"def (test_\w+)", content))
            except OSError:
                pass
        return names

    def _heuristic_check(
        self,
        criteria: list[str],
        recent_diff: str,
        test_names: list[str],
    ) -> DriftReport:
        """Check criteria against keywords found in diff + test names."""
        ok: list[str] = []
        drifted: list[str] = []

        diff_lower = recent_diff.lower()
        test_lower = " ".join(test_names).lower()
        combined = diff_lower + " " + test_lower

        for criterion in criteria:
            keywords = self._keywords_from_criterion(criterion)
            matched = sum(1 for kw in keywords if kw in combined)
            if keywords and matched / len(keywords) >= 0.4:
                ok.append(criterion)
            else:
                drifted.append(criterion)

        total = len(criteria)
        confidence = 0.6  # heuristic is inherently low confidence
        summary = (
            f"Heuristic check: {len(ok)}/{total} criteria appear satisfied "
            f"based on diff keywords and test names."
        )
        return DriftReport(
            drifted_criteria=drifted,
            ok_criteria=ok,
            confidence=confidence,
            summary=summary,
        )

    def _keywords_from_criterion(self, criterion: str) -> list[str]:
        """Extract meaningful keywords from an acceptance criterion."""
        # Remove boilerplate EARS phrases
        text = re.sub(
            r"\b(the system shall|when|if|it|should|must|the|a|an|and|or|is|are|be|to)\b",
            " ",
            criterion.lower(),
        )
        words = re.findall(r"[a-z_][a-z_0-9]+", text)
        return [w for w in words if len(w) >= 4]

    def _llm_check(
        self,
        criteria: list[str],
        recent_diff: str,
        test_names: list[str],
    ) -> DriftReport:
        """Use LLM to classify each criterion as ok/drifted."""
        import json

        criteria_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
        tests_sample = "\n".join(test_names[:50])
        diff_sample = recent_diff[:3000]

        messages = [
            {
                "role": "system",
                "content": (
                    "You classify spec drift.  Given acceptance criteria and recent code evidence, "
                    "return JSON: {\"ok\": [indices], \"drifted\": [indices]}  "
                    "(1-based indices into the criteria list)"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Acceptance criteria:\n{criteria_text}\n\n"
                    f"Recent git diff (excerpt):\n{diff_sample}\n\n"
                    f"Test names:\n{tests_sample}"
                ),
            },
        ]
        try:
            raw = self._llm(messages)
            text = raw.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(text)
            ok_idx = {i - 1 for i in data.get("ok", [])}
            drifted_idx = {i - 1 for i in data.get("drifted", [])}
            ok = [criteria[i] for i in range(len(criteria)) if i in ok_idx]
            drifted = [criteria[i] for i in range(len(criteria)) if i in drifted_idx]
            # Any unclassified → drifted (conservative)
            classified = ok_idx | drifted_idx
            for i in range(len(criteria)):
                if i not in classified:
                    drifted.append(criteria[i])
            return DriftReport(
                ok_criteria=ok,
                drifted_criteria=drifted,
                confidence=0.85,
                summary="LLM-based drift analysis complete.",
            )
        except Exception as exc:
            logger.warning("LLM drift check failed: %s — falling back to heuristic", exc)
            return self._heuristic_check(criteria, recent_diff, [])
