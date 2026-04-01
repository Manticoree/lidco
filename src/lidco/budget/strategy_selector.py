"""Select compaction strategy based on context pressure level."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PressureLevel(str, Enum):
    """Context-window pressure classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class StrategyConfig:
    """Configuration for a single compaction strategy."""

    name: str
    pressure: PressureLevel
    keep_recent: int = 10
    summarize_older: bool = False
    trim_tool_results: bool = True
    max_tool_result_tokens: int = 500
    collapse_similar: bool = False


_DEFAULT_STRATEGIES: dict[PressureLevel, StrategyConfig] = {
    PressureLevel.LOW: StrategyConfig(
        name="noop", pressure=PressureLevel.LOW,
        keep_recent=20, trim_tool_results=False,
    ),
    PressureLevel.MEDIUM: StrategyConfig(
        name="trim_tools", pressure=PressureLevel.MEDIUM,
        keep_recent=15, trim_tool_results=True, max_tool_result_tokens=500,
    ),
    PressureLevel.HIGH: StrategyConfig(
        name="summarize", pressure=PressureLevel.HIGH,
        keep_recent=8, summarize_older=True, trim_tool_results=True,
        max_tool_result_tokens=300, collapse_similar=True,
    ),
    PressureLevel.CRITICAL: StrategyConfig(
        name="aggressive", pressure=PressureLevel.CRITICAL,
        keep_recent=5, summarize_older=True, trim_tool_results=True,
        max_tool_result_tokens=100, collapse_similar=True,
    ),
}


class StrategySelector:
    """Map utilization to a compaction strategy."""

    def __init__(self) -> None:
        self._strategies: dict[PressureLevel, StrategyConfig] = dict(
            _DEFAULT_STRATEGIES
        )

    # -- classification -------------------------------------------------------

    def classify_pressure(self, utilization: float) -> PressureLevel:
        if utilization < 0.5:
            return PressureLevel.LOW
        if utilization < 0.7:
            return PressureLevel.MEDIUM
        if utilization < 0.9:
            return PressureLevel.HIGH
        return PressureLevel.CRITICAL

    def select(self, utilization: float) -> StrategyConfig:
        level = self.classify_pressure(utilization)
        return self._strategies[level]

    def register_strategy(self, config: StrategyConfig) -> None:
        self._strategies = {**self._strategies, config.pressure: config}

    def get_all(self) -> list[StrategyConfig]:
        return list(self._strategies.values())

    # -- application ----------------------------------------------------------

    def apply_to_messages(
        self, messages: list[dict], config: StrategyConfig
    ) -> list[dict]:
        """Apply *config* to a message list (immutable — returns new list)."""
        system: list[dict] = [m for m in messages if m.get("role") == "system"]
        non_system: list[dict] = [m for m in messages if m.get("role") != "system"]

        recent = non_system[-config.keep_recent:] if non_system else []
        older = non_system[: max(0, len(non_system) - config.keep_recent)]

        processed_older: list[dict] = []
        for msg in older:
            if config.trim_tool_results and msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                max_chars = config.max_tool_result_tokens * 4
                if len(content) > max_chars:
                    trimmed = content[:max_chars] + "... [trimmed]"
                    processed_older = [
                        *processed_older,
                        {**msg, "content": trimmed},
                    ]
                    continue
            if config.summarize_older and msg.get("role") == "assistant":
                content = str(msg.get("content", ""))
                if len(content) > 400:
                    processed_older = [
                        *processed_older,
                        {**msg, "content": content[:200] + "... [summarized]"},
                    ]
                    continue
            processed_older = [*processed_older, msg]

        return [*system, *processed_older, *recent]

    def summary(self) -> str:
        names = ", ".join(s.name for s in self._strategies.values())
        return f"StrategySelector: {len(self._strategies)} strategies ({names})"
