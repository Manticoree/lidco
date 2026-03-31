"""Bare mode — minimal startup, skip hooks/plugins/skills/mcp — Q171."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BareConfig:
    """Configuration for bare mode."""

    skip_hooks: bool = True
    skip_plugins: bool = True
    skip_skills: bool = True
    skip_mcp: bool = True
    minimal_context: bool = True


_FEATURE_FIELDS: dict[str, str] = {
    "hooks": "skip_hooks",
    "plugins": "skip_plugins",
    "skills": "skip_skills",
    "mcp": "skip_mcp",
    "context": "minimal_context",
}


class BareMode:
    """Toggle bare mode to skip optional subsystems for speed."""

    def __init__(self) -> None:
        self._active: bool = False
        self._config: BareConfig = BareConfig()
        self._activated_at: float | None = None
        self._skipped: list[str] = []

    # ------------------------------------------------------------------

    def activate(self, config: BareConfig | None = None) -> None:
        """Activate bare mode with the given (or default) config."""
        if config is not None:
            self._config = config
        self._active = True
        self._activated_at = time.monotonic()
        self._skipped = [
            feat
            for feat, attr in _FEATURE_FIELDS.items()
            if getattr(self._config, attr, False)
        ]

    def deactivate(self) -> None:
        """Deactivate bare mode."""
        self._active = False
        self._activated_at = None

    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Return whether bare mode is currently active."""
        return self._active

    def should_skip(self, feature: str) -> bool:
        """Return True if *feature* should be skipped under current config."""
        if not self._active:
            return False
        attr = _FEATURE_FIELDS.get(feature)
        if attr is None:
            return False
        return bool(getattr(self._config, attr, False))

    def get_config(self) -> BareConfig:
        """Return current bare-mode config."""
        return self._config

    def perf_summary(self) -> dict:
        """Return a summary of what is being skipped."""
        elapsed = 0.0
        if self._activated_at is not None:
            elapsed = time.monotonic() - self._activated_at
        return {
            "active": self._active,
            "skipped_features": list(self._skipped),
            "skipped_count": len(self._skipped),
            "elapsed": round(elapsed, 4),
            "config": {
                "skip_hooks": self._config.skip_hooks,
                "skip_plugins": self._config.skip_plugins,
                "skip_skills": self._config.skip_skills,
                "skip_mcp": self._config.skip_mcp,
                "minimal_context": self._config.minimal_context,
            },
        }
