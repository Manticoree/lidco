"""Update planner — risk assessment, rollback plans, and summaries."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdatePlan:
    """A single planned dependency update."""

    package: str
    current: str
    target: str
    risk: str
    breaking: bool = False


class UpdatePlanner:
    """Plan, assess, and summarise dependency updates."""

    def plan(self, updates: list[dict]) -> list[UpdatePlan]:
        """Convert raw update dicts into :class:`UpdatePlan` instances.

        Each dict must have ``package``, ``current``, and ``target`` keys.
        """
        plans: list[UpdatePlan] = []
        for u in updates:
            pkg = u["package"]
            cur = u["current"]
            tgt = u["target"]
            risk = self.risk_score(pkg, cur, tgt)
            breaking = _is_breaking(cur, tgt)
            plans = [*plans, UpdatePlan(package=pkg, current=cur, target=tgt, risk=risk, breaking=breaking)]
        return plans

    def risk_score(self, package: str, current: str, target: str) -> str:
        """Compute risk level based on semver distance.

        * Same major → ``"low"``
        * Different major, same first digit → ``"medium"``
        * Otherwise → ``"high"``
        """
        cur_parts = _parse_version(current)
        tgt_parts = _parse_version(target)
        if cur_parts[0] == tgt_parts[0]:
            return "low"
        if abs(cur_parts[0] - tgt_parts[0]) == 1:
            return "medium"
        return "high"

    def rollback_plan(self, plans: list[UpdatePlan]) -> list[dict]:
        """Generate rollback entries that revert each plan."""
        return [
            {"package": p.package, "from": p.target, "to": p.current}
            for p in plans
        ]

    def summary(self, plans: list[UpdatePlan]) -> str:
        """Human-readable summary of *plans*."""
        if not plans:
            return "No updates planned."
        breaking_count = sum(1 for p in plans if p.breaking)
        lines = [f"{len(plans)} update(s), {breaking_count} breaking:"]
        for p in plans:
            flag = " [BREAKING]" if p.breaking else ""
            lines = [*lines, f"  {p.package} {p.current} -> {p.target} ({p.risk}){flag}"]
        return "\n".join(lines)


def _parse_version(v: str) -> tuple[int, int, int]:
    """Parse a dotted version into a 3-tuple of ints."""
    parts = v.split(".")
    nums: list[int] = []
    for p in parts[:3]:
        try:
            nums = [*nums, int(p)]
        except ValueError:
            nums = [*nums, 0]
    while len(nums) < 3:
        nums = [*nums, 0]
    return (nums[0], nums[1], nums[2])


def _is_breaking(current: str, target: str) -> bool:
    """Return True when the major version differs."""
    return _parse_version(current)[0] != _parse_version(target)[0]
