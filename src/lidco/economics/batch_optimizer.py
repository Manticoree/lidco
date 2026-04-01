"""Batch Request Optimizer — detect independent sub-tasks, batch, deduplicate context, report savings."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatchRequest:
    """A single request to be batched."""

    id: str
    content: str
    context: dict = field(default_factory=dict)
    priority: int = 0
    group: str = "default"


@dataclass(frozen=True)
class BatchGroup:
    """A group of requests that share context."""

    name: str
    requests: tuple[BatchRequest, ...]
    shared_context: dict = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of a batch optimization pass."""

    groups: list[BatchGroup] = field(default_factory=list)
    total_requests: int = 0
    deduplicated_tokens: int = 0
    estimated_savings_pct: float = 0.0


class BatchOptimizer:
    """Detect independent sub-tasks, batch them, deduplicate context, report savings."""

    def __init__(self) -> None:
        self._requests: list[BatchRequest] = []
        self._groups: dict[str, list[BatchRequest]] = {}
        self._results: list[BatchResult] = []

    def add_request(self, request: BatchRequest) -> None:
        """Add a request to the optimizer."""
        self._requests.append(request)

    def group_requests(self) -> list[BatchGroup]:
        """Group requests by their group field and merge shared context keys."""
        buckets: dict[str, list[BatchRequest]] = {}
        for req in self._requests:
            buckets.setdefault(req.group, []).append(req)

        groups: list[BatchGroup] = []
        for name, reqs in buckets.items():
            # Find context keys common to all requests in this group
            shared: dict = {}
            if reqs:
                if reqs[0].context:
                    shared = dict(reqs[0].context)
                    for req in reqs[1:]:
                        shared = {
                            k: v
                            for k, v in shared.items()
                            if k in req.context and req.context[k] == v
                        }

            groups.append(
                BatchGroup(
                    name=name,
                    requests=tuple(sorted(reqs, key=lambda r: -r.priority)),
                    shared_context=shared,
                )
            )
        return groups

    def deduplicate_context(self, groups: list[BatchGroup]) -> list[BatchGroup]:
        """Find common context keys across groups and extract as shared context."""
        if len(groups) < 2:
            return groups

        # Find keys common across ALL groups' shared contexts
        common: dict = dict(groups[0].shared_context)
        for grp in groups[1:]:
            common = {
                k: v
                for k, v in common.items()
                if k in grp.shared_context and grp.shared_context[k] == v
            }

        if not common:
            return groups

        # Remove common keys from individual group shared_context
        deduped: list[BatchGroup] = []
        for grp in groups:
            remaining = {k: v for k, v in grp.shared_context.items() if k not in common}
            deduped.append(
                BatchGroup(
                    name=grp.name,
                    requests=grp.requests,
                    shared_context=remaining,
                )
            )
        return deduped

    def optimize(self) -> BatchResult:
        """Run full optimization: group, deduplicate, return result."""
        groups = self.group_requests()
        deduped = self.deduplicate_context(groups)

        total = len(self._requests)
        # Estimate deduplication savings based on shared context tokens removed
        total_context_chars = sum(
            sum(len(str(v)) for v in req.context.values())
            for req in self._requests
        )
        deduped_chars = sum(
            sum(len(str(v)) for v in grp.shared_context.values()) * len(grp.requests)
            for grp in groups
        )
        saved = max(0, total_context_chars - deduped_chars) if total_context_chars > 0 else 0
        savings_pct = (saved / total_context_chars * 100) if total_context_chars > 0 else 0.0

        result = BatchResult(
            groups=deduped,
            total_requests=total,
            deduplicated_tokens=saved,
            estimated_savings_pct=round(savings_pct, 1),
        )
        self._results.append(result)
        return result

    def clear(self) -> None:
        """Reset all state."""
        self._requests.clear()
        self._groups.clear()
        self._results.clear()

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"Requests: {len(self._requests)}"]
        lines.append(f"Optimizations run: {len(self._results)}")
        if self._results:
            last = self._results[-1]
            lines.append(f"Last result: {len(last.groups)} groups, {last.total_requests} requests")
            lines.append(f"  Deduped tokens: {last.deduplicated_tokens}, savings: {last.estimated_savings_pct}%")
        return "\n".join(lines)
