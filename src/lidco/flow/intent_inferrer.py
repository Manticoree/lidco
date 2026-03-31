"""Intent Inferrer — determines what the user is currently doing."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.flow.action_tracker import ActionTracker


@dataclass
class InferredIntent:
    """Result of intent inference."""

    intent: str  # debugging, refactoring, feature_dev, reviewing, exploring, testing
    confidence: float
    evidence: list[str] = field(default_factory=list)


class IntentInferrer:
    """Analyzes recent actions to infer developer intent."""

    def __init__(self, tracker: ActionTracker) -> None:
        self._tracker = tracker

    def infer(self) -> InferredIntent:
        """Analyze recent actions and return the most likely intent."""
        recent = self._tracker.recent(limit=30)
        if not recent:
            return InferredIntent(intent="exploring", confidence=0.1, evidence=["no actions recorded"])

        error_rate = self._tracker.error_rate(window=30)
        type_counts: dict[str, int] = {}
        file_counts: dict[str, int] = {}
        for a in recent:
            type_counts[a.action_type] = type_counts.get(a.action_type, 0) + 1
            if a.file_path:
                file_counts[a.file_path] = file_counts.get(a.file_path, 0) + 1

        total = len(recent)
        edits = type_counts.get("edit", 0)
        reads = type_counts.get("read", 0)
        errors = type_counts.get("error", 0)
        commands = type_counts.get("command", 0)
        searches = type_counts.get("search", 0)

        # Check for test files in edits
        test_file_edits = sum(
            1 for a in recent
            if a.action_type == "edit" and a.file_path and "test" in a.file_path.lower()
        )

        candidates: list[tuple[str, float, list[str]]] = []

        # Debugging: many errors + reads
        if errors > 0 or error_rate > 0.15:
            conf = min(0.95, 0.3 + error_rate * 1.5)
            evidence = [f"error_rate={error_rate:.0%}", f"{errors} error actions"]
            if reads > edits:
                conf += 0.1
                evidence.append("more reads than edits")
            candidates.append(("debugging", min(conf, 0.95), evidence))

        # Refactoring: many edits to same file
        if edits > 0 and file_counts:
            max_file_count = max(file_counts.values())
            if max_file_count >= 3 and edits / total > 0.3:
                conf = min(0.9, 0.4 + (max_file_count / total))
                top_file = max(file_counts, key=file_counts.get)  # type: ignore[arg-type]
                candidates.append(("refactoring", conf, [
                    f"{max_file_count} actions on {top_file}",
                    f"{edits} edits total",
                ]))

        # Feature dev: new file creates + edits spread across files
        new_creates = sum(1 for a in recent if a.detail.startswith("create"))
        if new_creates > 0 and edits > 0:
            conf = min(0.85, 0.3 + new_creates * 0.15 + edits * 0.05)
            candidates.append(("feature_dev", conf, [
                f"{new_creates} new file creates",
                f"{edits} edits across files",
            ]))

        # Testing: test file edits + command runs
        if test_file_edits > 0 and commands > 0:
            conf = min(0.85, 0.3 + test_file_edits * 0.15 + commands * 0.1)
            candidates.append(("testing", conf, [
                f"{test_file_edits} test file edits",
                f"{commands} command runs",
            ]))

        # Reviewing/exploring: mostly reads, few edits
        if reads > 0 and reads > edits:
            read_ratio = reads / total
            conf = min(0.8, 0.2 + read_ratio)
            intent_name = "reviewing" if searches > 0 else "exploring"
            candidates.append((intent_name, conf, [
                f"{reads} reads ({read_ratio:.0%} of actions)",
                f"{edits} edits",
            ]))

        if not candidates:
            return InferredIntent(intent="exploring", confidence=0.2, evidence=["no strong signal"])

        # Pick highest confidence
        candidates.sort(key=lambda c: c[1], reverse=True)
        best = candidates[0]
        return InferredIntent(intent=best[0], confidence=round(best[1], 2), evidence=best[2])

    def explain(self) -> str:
        """Return a human-readable explanation of the current inferred intent."""
        result = self.infer()
        evidence_str = "; ".join(result.evidence)
        return (
            f"Current intent: {result.intent} "
            f"(confidence: {result.confidence:.0%}). "
            f"Evidence: {evidence_str}."
        )
