"""Q169 Task 959 — PR Assembler."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.cloud.agent_spawner import AgentHandle
from lidco.cloud.status_tracker import AgentLog


@dataclass
class PRDraft:
    """Draft of a pull request."""

    title: str
    body: str
    branch: str
    base_branch: str
    files_changed: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0


class PRAssembler:
    """Assembles PR drafts from agent results."""

    def __init__(self, base_branch: str = "main") -> None:
        self.base_branch = base_branch

    def assemble(self, agent_handle: AgentHandle, agent_log: AgentLog) -> PRDraft:
        """Assemble a complete PR draft from agent handle and log."""
        files = self._extract_files(agent_log.diff)
        additions, deletions = self.count_changes(agent_log.diff)
        title = self.generate_title(agent_handle.prompt, files)
        body = self.generate_body(agent_handle.prompt, agent_log)
        branch = agent_handle.branch_name or f"agent/{agent_handle.agent_id}"
        return PRDraft(
            title=title,
            body=body,
            branch=branch,
            base_branch=self.base_branch,
            files_changed=files,
            additions=additions,
            deletions=deletions,
        )

    def generate_title(self, prompt: str, files: list[str]) -> str:
        """Generate a concise PR title from the prompt."""
        text = prompt.strip()
        if len(text) > 70:
            text = text[:67] + "..."
        return text

    def generate_body(self, prompt: str, log: AgentLog) -> str:
        """Generate a markdown PR body."""
        sections: list[str] = []
        sections.append("## Summary")
        sections.append(f"Agent task: {prompt}")
        sections.append("")
        if log.entries:
            sections.append("## Agent Log")
            for entry in log.entries[-10:]:
                sections.append(f"- {entry}")
            sections.append("")
        if log.output:
            sections.append("## Output")
            sections.append(log.output)
            sections.append("")
        if log.diff:
            files = self._extract_files(log.diff)
            if files:
                sections.append("## Files Changed")
                for f in files:
                    sections.append(f"- `{f}`")
                sections.append("")
        sections.append("## Test Plan")
        sections.append("- [ ] Verify changes match the original prompt")
        sections.append("- [ ] Run test suite")
        sections.append("- [ ] Review diff for correctness")
        return "\n".join(sections)

    def count_changes(self, diff: str) -> tuple[int, int]:
        """Count additions and deletions from a unified diff."""
        additions = 0
        deletions = 0
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        return additions, deletions

    def _extract_files(self, diff: str) -> list[str]:
        """Extract file paths from diff headers."""
        files: list[str] = []
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:].strip()
                if path and path not in files:
                    files.append(path)
            elif line.startswith("--- a/"):
                path = line[6:].strip()
                if path and path not in files:
                    files.append(path)
        return files
