"""Hard limits on tool result sizes with progressive shrinking."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LimitConfig:
    """Per-tool limit configuration."""

    tool_name: str
    max_tokens: int = 2000
    min_tokens: int = 200
    shrink_at_utilization: float = 0.7


@dataclass(frozen=True)
class LimitResult:
    """Outcome of applying a result limit."""

    tool_name: str
    original_tokens: int
    limited_tokens: int
    was_limited: bool = False
    effective_limit: int = 2000


class ResultLimiter:
    """Enforce hard limits on tool result sizes.

    When context-window utilization exceeds a tool's ``shrink_at_utilization``
    threshold the effective limit shrinks linearly from *max_tokens* toward
    *min_tokens* as utilization approaches 1.0.
    """

    def __init__(self) -> None:
        self._configs: dict[str, LimitConfig] = {
            "Read": LimitConfig(tool_name="Read", max_tokens=2000, min_tokens=200),
            "Grep": LimitConfig(tool_name="Grep", max_tokens=1000, min_tokens=200),
            "Bash": LimitConfig(tool_name="Bash", max_tokens=1500, min_tokens=200),
            "Glob": LimitConfig(tool_name="Glob", max_tokens=500, min_tokens=100),
        }
        self._default_config = LimitConfig(tool_name="default", max_tokens=2000, min_tokens=200)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_config(self, config: LimitConfig) -> None:
        """Register or replace a per-tool limit configuration."""
        self._configs = {**self._configs, config.tool_name: config}

    def get_limit(self, tool_name: str, utilization: float = 0.0) -> int:
        """Compute the effective token limit given current *utilization* (0–1)."""
        cfg = self._configs.get(tool_name, self._default_config)
        if utilization <= cfg.shrink_at_utilization:
            return cfg.max_tokens
        # Linear shrink from max → min as utilization goes from threshold → 1.0
        span = 1.0 - cfg.shrink_at_utilization
        if span <= 0:
            return cfg.min_tokens
        progress = min((utilization - cfg.shrink_at_utilization) / span, 1.0)
        effective = cfg.max_tokens - int(progress * (cfg.max_tokens - cfg.min_tokens))
        return max(effective, cfg.min_tokens)

    def apply(
        self, tool_name: str, content: str, utilization: float = 0.0
    ) -> tuple[str, LimitResult]:
        """Truncate *content* to the effective limit; return *(text, metadata)*."""
        original_tokens = self.estimate_tokens(content)
        effective = self.get_limit(tool_name, utilization)

        if original_tokens <= effective:
            return content, LimitResult(
                tool_name=tool_name,
                original_tokens=original_tokens,
                limited_tokens=original_tokens,
                was_limited=False,
                effective_limit=effective,
            )

        max_chars = effective * 4
        truncated = content[:max_chars] + "\n... [limited] ..."
        return truncated, LimitResult(
            tool_name=tool_name,
            original_tokens=original_tokens,
            limited_tokens=self.estimate_tokens(truncated),
            was_limited=True,
            effective_limit=effective,
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        return len(text) // 4

    def summary(self) -> str:
        """Human-readable summary of configured limits."""
        parts: list[str] = []
        for name in sorted(self._configs):
            cfg = self._configs[name]
            parts.append(
                f"{name}: max={cfg.max_tokens}, min={cfg.min_tokens}, "
                f"shrink_at={cfg.shrink_at_utilization}"
            )
        return "ResultLimiter: " + " | ".join(parts)
