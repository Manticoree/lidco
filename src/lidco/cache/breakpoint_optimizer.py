"""Breakpoint Optimizer — find optimal cache breakpoints in prompts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Breakpoint:
    """A suggested cache breakpoint in a prompt."""

    position: int
    savings_estimate: float
    description: str


class BreakpointOptimizer:
    """Analyze prompts for optimal cache breakpoint positions.

    Breakpoints are placed at paragraph/section boundaries to maximize
    cache reuse when prompt prefixes are shared across calls.
    """

    def analyze(
        self, prompt: str, cache_prefix_len: int = 0
    ) -> tuple[Breakpoint, ...]:
        """Find candidate breakpoints in *prompt*.

        Parameters
        ----------
        prompt:
            The full prompt text.
        cache_prefix_len:
            Length of the already-cached prefix (positions before this are skipped).
        """
        breakpoints: list[Breakpoint] = []
        lines = prompt.split("\n")
        pos = 0
        for i, line in enumerate(lines):
            pos += len(line) + 1  # +1 for newline
            if pos <= cache_prefix_len:
                continue
            stripped = line.strip()
            if not stripped and i > 0:
                # Paragraph boundary
                savings = (pos / len(prompt)) if prompt else 0.0
                breakpoints.append(
                    Breakpoint(
                        position=pos,
                        savings_estimate=round(savings, 4),
                        description=f"paragraph boundary at line {i + 1}",
                    )
                )
            elif stripped.startswith("#") or stripped.startswith("---"):
                savings = (pos / len(prompt)) if prompt else 0.0
                breakpoints.append(
                    Breakpoint(
                        position=pos,
                        savings_estimate=round(savings, 4),
                        description=f"section header at line {i + 1}",
                    )
                )
        return tuple(breakpoints)

    def optimal_split(self, prompt: str, num_parts: int = 2) -> tuple[str, ...]:
        """Split *prompt* into *num_parts* at optimal breakpoints."""
        if num_parts < 2 or not prompt:
            return (prompt,)
        breakpoints = self.analyze(prompt)
        if not breakpoints:
            # Fallback: split evenly
            chunk = len(prompt) // num_parts
            parts = []
            for i in range(num_parts):
                start = i * chunk
                end = start + chunk if i < num_parts - 1 else len(prompt)
                parts.append(prompt[start:end])
            return tuple(parts)

        # Pick the breakpoint closest to each ideal split point
        ideal_positions = [
            (len(prompt) * (i + 1)) // num_parts for i in range(num_parts - 1)
        ]
        chosen: list[int] = []
        for ideal in ideal_positions:
            best = min(breakpoints, key=lambda bp: abs(bp.position - ideal))
            if best.position not in chosen:
                chosen.append(best.position)

        chosen.sort()
        parts: list[str] = []
        prev = 0
        for pos in chosen:
            parts.append(prompt[prev:pos])
            prev = pos
        parts.append(prompt[prev:])
        return tuple(p for p in parts if p)


__all__ = ["Breakpoint", "BreakpointOptimizer"]
