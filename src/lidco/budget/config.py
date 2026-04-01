"""Budget configuration with defaults and per-model overrides."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetConfig:
    """Immutable budget configuration."""

    context_limit: int = 128_000
    warn_threshold: float = 0.70
    critical_threshold: float = 0.85
    emergency_threshold: float = 0.95
    max_tool_result_tokens: int = 2000
    debt_ceiling: int = 50_000
    auto_compact: bool = True
    compact_strategy: str = "balanced"


_CONFIG_FIELDS = (
    "context_limit", "warn_threshold", "critical_threshold",
    "emergency_threshold", "max_tool_result_tokens", "debt_ceiling",
    "auto_compact", "compact_strategy",
)


class BudgetConfigManager:
    """Manage default and per-model budget configurations."""

    def __init__(self, default: BudgetConfig | None = None) -> None:
        self._default = default or BudgetConfig()
        self._overrides: dict[str, BudgetConfig] = {}

    def get(self, model: str | None = None) -> BudgetConfig:
        """Return override for *model* if it exists, else default."""
        if model is not None and model in self._overrides:
            return self._overrides[model]
        return self._default

    def set_override(self, model: str, config: BudgetConfig) -> None:
        """Set a per-model override."""
        self._overrides = {**self._overrides, model: config}

    def remove_override(self, model: str) -> bool:
        """Remove a per-model override. Return True if it existed."""
        if model not in self._overrides:
            return False
        self._overrides = {k: v for k, v in self._overrides.items() if k != model}
        return True

    def list_overrides(self) -> dict[str, BudgetConfig]:
        """Return all per-model overrides."""
        return dict(self._overrides)

    def from_dict(self, data: dict) -> BudgetConfig:
        """Parse a dict into a BudgetConfig, using defaults for missing keys."""
        kwargs = {}
        for f in _CONFIG_FIELDS:
            if f in data:
                kwargs[f] = data[f]
        return BudgetConfig(**kwargs)

    def to_dict(self, config: BudgetConfig) -> dict:
        """Serialize a BudgetConfig to a plain dict."""
        return {f: getattr(config, f) for f in _CONFIG_FIELDS}

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"BudgetConfig: limit={self._default.context_limit:,}, "
            f"thresholds={self._default.warn_threshold}/{self._default.critical_threshold}/{self._default.emergency_threshold}, "
            f"strategy={self._default.compact_strategy}",
        ]
        if self._overrides:
            lines.append(f"  Overrides: {', '.join(sorted(self._overrides))}")
        return "\n".join(lines)
