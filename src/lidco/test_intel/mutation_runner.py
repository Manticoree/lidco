"""AST-based mutation testing."""
from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field


class MutationType(str, enum.Enum):
    """Categories of source-code mutations."""

    NEGATE_CONDITION = "NEGATE_CONDITION"
    SWAP_OPERATOR = "SWAP_OPERATOR"
    DELETE_STATEMENT = "DELETE_STATEMENT"
    CHANGE_CONSTANT = "CHANGE_CONSTANT"
    BOUNDARY_CHANGE = "BOUNDARY_CHANGE"


@dataclass(frozen=True)
class Mutant:
    """A single mutation applied to source code."""

    id: str
    type: MutationType
    file: str = ""
    line: int = 0
    original: str = ""
    mutated: str = ""
    killed: bool = False


# Operator swap pairs.
_OPERATOR_SWAPS: list[tuple[str, str]] = [
    ("+", "-"),
    ("-", "+"),
    ("*", "/"),
    ("/", "*"),
    ("==", "!="),
    ("!=", "=="),
    ("<=", ">"),
    (">=", "<"),
    ("<", ">="),
    (">", "<="),
    (" and ", " or "),
    (" or ", " and "),
]


class MutationRunner:
    """Generate and track source-code mutants."""

    def __init__(self) -> None:
        self._killed: set[str] = set()

    def generate_mutants(self, source: str, file: str = "") -> list[Mutant]:
        """Apply mutation operators to *source* and return mutants."""
        mutants: list[Mutant] = []

        for line_no, orig, mut in self._negate_conditions(source):
            mutants.append(Mutant(
                id=uuid.uuid4().hex[:12],
                type=MutationType.NEGATE_CONDITION,
                file=file,
                line=line_no,
                original=orig,
                mutated=mut,
            ))

        for line_no, orig, mut in self._swap_operators(source):
            mutants.append(Mutant(
                id=uuid.uuid4().hex[:12],
                type=MutationType.SWAP_OPERATOR,
                file=file,
                line=line_no,
                original=orig,
                mutated=mut,
            ))

        for line_no, orig, mut in self._change_constants(source):
            mutants.append(Mutant(
                id=uuid.uuid4().hex[:12],
                type=MutationType.CHANGE_CONSTANT,
                file=file,
                line=line_no,
                original=orig,
                mutated=mut,
            ))

        for line_no, orig, mut in self._boundary_changes(source):
            mutants.append(Mutant(
                id=uuid.uuid4().hex[:12],
                type=MutationType.BOUNDARY_CHANGE,
                file=file,
                line=line_no,
                original=orig,
                mutated=mut,
            ))

        return mutants

    def _negate_conditions(self, source: str) -> list[tuple[int, str, str]]:
        """Find ``if`` conditions and negate them."""
        results: list[tuple[int, str, str]] = []
        for idx, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            m = re.match(r"^(if|elif|while)\s+(.+):\s*$", stripped)
            if m:
                keyword, cond = m.group(1), m.group(2)
                negated = f"{keyword} not ({cond}):"
                results.append((idx, stripped, negated))
        return results

    def _swap_operators(self, source: str) -> list[tuple[int, str, str]]:
        """Swap arithmetic / comparison / logical operators."""
        results: list[tuple[int, str, str]] = []
        for idx, line in enumerate(source.splitlines(), 1):
            for old_op, new_op in _OPERATOR_SWAPS:
                if old_op in line:
                    mutated = line.replace(old_op, new_op, 1)
                    if mutated != line:
                        results.append((idx, line.strip(), mutated.strip()))
                        break  # one swap per line
        return results

    def _change_constants(self, source: str) -> list[tuple[int, str, str]]:
        """Replace numeric constants with boundary-adjacent values."""
        results: list[tuple[int, str, str]] = []
        for idx, line in enumerate(source.splitlines(), 1):
            for m in re.finditer(r"\b(\d+)\b", line):
                val = int(m.group(1))
                new_val = val + 1
                mutated = line[: m.start()] + str(new_val) + line[m.end() :]
                results.append((idx, line.strip(), mutated.strip()))
                break  # one constant change per line
        return results

    def _boundary_changes(self, source: str) -> list[tuple[int, str, str]]:
        """Shift boundary comparisons by one."""
        results: list[tuple[int, str, str]] = []
        for idx, line in enumerate(source.splitlines(), 1):
            m = re.search(r"([<>]=?)\s*(\d+)", line)
            if m:
                op = m.group(1)
                val = int(m.group(2))
                new_val = val + 1 if "<" in op else val - 1
                mutated = line[: m.start(2)] + str(new_val) + line[m.end(2) :]
                if mutated != line:
                    results.append((idx, line.strip(), mutated.strip()))
        return results

    def mark_killed(self, mutant_id: str) -> None:
        """Record that *mutant_id* was killed by a test."""
        self._killed.add(mutant_id)

    def survival_report(self, mutants: list[Mutant]) -> str:
        """Return a human-readable survival report."""
        lines: list[str] = [f"Mutation Report ({len(mutants)} mutants)"]
        lines.append(f"Score: {self.mutation_score(mutants):.1%}")
        lines.append("")
        survived = [m for m in mutants if m.id not in self._killed and not m.killed]
        if survived:
            lines.append("Surviving mutants:")
            for m in survived:
                lines.append(f"  [{m.type.value}] {m.file}:{m.line} {m.original!r} -> {m.mutated!r}")
        else:
            lines.append("All mutants killed!")
        return "\n".join(lines)

    def mutation_score(self, mutants: list[Mutant]) -> float:
        """Return killed/total ratio."""
        if not mutants:
            return 1.0
        killed = sum(1 for m in mutants if m.id in self._killed or m.killed)
        return killed / len(mutants)
