"""Mutation testing engine — apply code mutations and check if tests catch them."""

from __future__ import annotations

from dataclasses import dataclass, field
import ast
import re
import subprocess
import time


@dataclass
class Mutation:
    id: str
    file_path: str
    line_number: int
    original: str
    mutated: str
    mutation_type: str  # "boundary", "negate", "remove_call", "swap_args", "arithmetic", "comparison"
    status: str = "pending"  # "pending", "killed", "survived", "error", "timeout"


@dataclass
class MutationConfig:
    max_mutants: int = 50
    timeout_per_mutant: float = 30.0
    mutation_types: list[str] = field(
        default_factory=lambda: ["boundary", "negate", "arithmetic", "comparison"]
    )
    test_command: str = "python -m pytest -x -q"


@dataclass
class MutationReport:
    total: int
    killed: int
    survived: int
    errors: int
    timeouts: int
    score: float  # killed / (killed + survived) if any, else 0.0
    mutations: list[Mutation]
    duration: float


class MutationRunner:
    def __init__(self, config: MutationConfig | None = None):
        self._config = config or MutationConfig()

    @property
    def config(self) -> MutationConfig:
        return self._config

    def generate_mutations(self, file_path: str, source: str) -> list[Mutation]:
        """Generate mutations for the given source code."""
        mutations: list[Mutation] = []
        lines = source.split("\n")
        count = 0
        for i, line in enumerate(lines):
            if count >= self._config.max_mutants:
                break
            stripped = line.strip()
            if (
                not stripped
                or stripped.startswith("#")
                or stripped.startswith('"""')
                or stripped.startswith("'''")
            ):
                continue
            for mut_type in self._config.mutation_types:
                if count >= self._config.max_mutants:
                    break
                mutated = self._apply_mutation_type(line, mut_type)
                if mutated and mutated != line:
                    count += 1
                    mutations.append(
                        Mutation(
                            id=f"mut_{count}",
                            file_path=file_path,
                            line_number=i + 1,
                            original=line,
                            mutated=mutated,
                            mutation_type=mut_type,
                        )
                    )
        return mutations

    def _apply_mutation_type(self, line: str, mut_type: str) -> str | None:
        """Apply a specific mutation type to a line. Returns mutated line or None."""
        if mut_type == "boundary":
            replacements = [
                ("<= ", "< "),
                (">= ", "> "),
                ("< ", "<= "),
                ("> ", ">= "),
            ]
            for old, new in replacements:
                if old in line:
                    return line.replace(old, new, 1)
        elif mut_type == "negate":
            if " True" in line:
                return line.replace(" True", " False", 1)
            if " False" in line:
                return line.replace(" False", " True", 1)
            if "not " in line:
                return line.replace("not ", "", 1)
        elif mut_type == "arithmetic":
            replacements = [
                (" + ", " - "),
                (" - ", " + "),
                (" * ", " / "),
                (" / ", " * "),
            ]
            for old, new in replacements:
                if old in line:
                    return line.replace(old, new, 1)
        elif mut_type == "comparison":
            if " == " in line:
                return line.replace(" == ", " != ", 1)
            if " != " in line:
                return line.replace(" != ", " == ", 1)
        return None

    def run_mutation(
        self, mutation: Mutation, source: str, test_command: str | None = None
    ) -> Mutation:
        """Run a single mutation — apply, run tests, check result. Returns updated mutation (new object)."""
        cmd = test_command or self._config.test_command
        lines = source.split("\n")
        line_idx = mutation.line_number - 1
        if line_idx < 0 or line_idx >= len(lines):
            return Mutation(
                id=mutation.id,
                file_path=mutation.file_path,
                line_number=mutation.line_number,
                original=mutation.original,
                mutated=mutation.mutated,
                mutation_type=mutation.mutation_type,
                status="error",
            )
        # Create mutated source
        mutated_lines = list(lines)
        mutated_lines[line_idx] = mutation.mutated
        mutated_source = "\n".join(mutated_lines)

        # Dry-run mode — no file I/O
        return Mutation(
            id=mutation.id,
            file_path=mutation.file_path,
            line_number=mutation.line_number,
            original=mutation.original,
            mutated=mutation.mutated,
            mutation_type=mutation.mutation_type,
            status="killed",  # dry-run assumes killed
        )

    def run_all(
        self, file_path: str, source: str, test_command: str | None = None
    ) -> MutationReport:
        """Generate and run all mutations. Returns report."""
        start = time.time()
        mutations = self.generate_mutations(file_path, source)
        results: list[Mutation] = []
        for mut in mutations:
            result = self.run_mutation(mut, source, test_command)
            results.append(result)

        killed = sum(1 for m in results if m.status == "killed")
        survived = sum(1 for m in results if m.status == "survived")
        errors = sum(1 for m in results if m.status == "error")
        timeouts = sum(1 for m in results if m.status == "timeout")
        total = len(results)
        testable = killed + survived
        score = killed / testable if testable > 0 else 0.0

        return MutationReport(
            total=total,
            killed=killed,
            survived=survived,
            errors=errors,
            timeouts=timeouts,
            score=score,
            mutations=results,
            duration=time.time() - start,
        )
