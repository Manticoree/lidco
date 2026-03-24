"""Cost projector for LLM operations -- Task 586.

Estimates token usage, cost, and time for planned LLM steps using
heuristic token counts and optional historical data.

Usage::

    proj = CostProjector(model="gpt-4o")
    est = proj.estimate_step("analyze code", context_files=5)
    print(est.estimated_cost_usd)

    projection = proj.estimate_plan([
        {"name": "analyze", "context_files": 3},
        {"name": "implement", "output_lines": 80},
    ])
    print(projection.format_summary())
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ModelPricing:
    """Pricing info for a single model."""

    model: str
    input_per_1k: float  # USD per 1K input tokens
    output_per_1k: float  # USD per 1K output tokens
    tokens_per_second: float  # output tokens per second (for time estimation)


@dataclass
class StepEstimate:
    """Estimated cost/time for a single step."""

    step_name: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    estimated_seconds: float
    confidence: float  # 0.0-1.0


@dataclass
class CostProjection:
    """Aggregated projection across multiple steps."""

    steps: list[StepEstimate]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_seconds: float
    model: str
    confidence: float  # average across steps

    def format_summary(self) -> str:
        """Human-readable one-liner.

        Returns something like:
            Estimated: ~$0.42, ~45s, ~12K tokens (medium confidence)

        Confidence labels: <0.4 = low, 0.4-0.7 = medium, >0.7 = high.
        """
        total_tokens = self.total_input_tokens + self.total_output_tokens
        if total_tokens >= 1000:
            token_str = f"~{total_tokens // 1000}K tokens"
        else:
            token_str = f"~{total_tokens} tokens"

        if self.confidence < 0.4:
            label = "low"
        elif self.confidence <= 0.7:
            label = "medium"
        else:
            label = "high"

        return (
            f"Estimated: ~${self.total_cost_usd:.2f}, "
            f"~{self.total_seconds:.0f}s, "
            f"{token_str} ({label} confidence)"
        )

    def format_detailed(self) -> str:
        """Per-step table with a TOTAL row."""
        header = f"{'Step':<30} {'Input':>8} {'Output':>8} {'Cost':>10} {'Time':>8}"
        sep = "-" * len(header)
        lines = [header, sep]
        for s in self.steps:
            lines.append(
                f"{s.step_name:<30} {s.estimated_input_tokens:>8} "
                f"{s.estimated_output_tokens:>8} "
                f"${s.estimated_cost_usd:>8.4f} "
                f"{s.estimated_seconds:>6.0f}s"
            )
        lines.append(sep)
        lines.append(
            f"{'TOTAL':<30} {self.total_input_tokens:>8} "
            f"{self.total_output_tokens:>8} "
            f"${self.total_cost_usd:>8.4f} "
            f"{self.total_seconds:>6.0f}s"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default pricing table
# ---------------------------------------------------------------------------

DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gpt-4o": ModelPricing("gpt-4o", input_per_1k=0.0025, output_per_1k=0.01, tokens_per_second=50.0),
    "gpt-4o-mini": ModelPricing("gpt-4o-mini", input_per_1k=0.00015, output_per_1k=0.0006, tokens_per_second=100.0),
    "claude-sonnet-4": ModelPricing("claude-sonnet-4", input_per_1k=0.003, output_per_1k=0.015, tokens_per_second=60.0),
    "claude-opus-4": ModelPricing("claude-opus-4", input_per_1k=0.015, output_per_1k=0.075, tokens_per_second=20.0),
    "claude-haiku-4": ModelPricing("claude-haiku-4", input_per_1k=0.0008, output_per_1k=0.004, tokens_per_second=120.0),
}


# ---------------------------------------------------------------------------
# CostProjector
# ---------------------------------------------------------------------------


class CostProjector:
    """Estimates LLM cost and time for planned operations."""

    # Heuristic constants
    BASE_INPUT_TOKENS: int = 500
    TOKENS_PER_CONTEXT_FILE: int = 400
    TOKENS_PER_OUTPUT_LINE: int = 15
    DEFAULT_OUTPUT_TOKENS: int = 300

    def __init__(
        self,
        model: str = "gpt-4o",
        pricing: dict[str, ModelPricing] | None = None,
        history_path: Path | None = None,
    ) -> None:
        self.model = model
        self.pricing = pricing if pricing is not None else dict(DEFAULT_PRICING)
        self.history_path = history_path
        self._history: dict = self._load_history()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate_step(
        self,
        description: str,
        context_files: int = 0,
        expected_output_lines: int = 0,
    ) -> StepEstimate:
        """Estimate tokens and cost for a single step.

        If history has samples for an exact ``description`` match, the
        historical average is used and confidence is set to 0.9.
        Otherwise a heuristic is applied with confidence 0.3.
        """
        pricing = self._get_pricing()

        # Check history for this exact step name
        hist_entry = self._history.get(description)
        if hist_entry and hist_entry.get("samples"):
            samples = hist_entry["samples"]
            avg_input = int(sum(s["input"] for s in samples) / len(samples))
            avg_output = int(sum(s["output"] for s in samples) / len(samples))
            avg_elapsed = sum(s["elapsed"] for s in samples) / len(samples)
            cost = (
                avg_input * pricing.input_per_1k / 1000
                + avg_output * pricing.output_per_1k / 1000
            )
            return StepEstimate(
                step_name=description,
                estimated_input_tokens=avg_input,
                estimated_output_tokens=avg_output,
                estimated_cost_usd=cost,
                estimated_seconds=avg_elapsed,
                confidence=0.9,
            )

        # Heuristic estimation
        word_count = len(description.split())
        input_tokens = (
            self.BASE_INPUT_TOKENS
            + context_files * self.TOKENS_PER_CONTEXT_FILE
            + word_count * 2
        )
        output_tokens = max(
            self.DEFAULT_OUTPUT_TOKENS,
            expected_output_lines * self.TOKENS_PER_OUTPUT_LINE,
        )
        cost = (
            input_tokens * pricing.input_per_1k / 1000
            + output_tokens * pricing.output_per_1k / 1000
        )
        seconds = output_tokens / pricing.tokens_per_second

        return StepEstimate(
            step_name=description,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=cost,
            estimated_seconds=seconds,
            confidence=0.3,
        )

    def estimate_plan(self, steps: list[dict]) -> CostProjection:
        """Estimate cost for a list of step dicts.

        Each dict: ``{"name": str, "context_files": int, "output_lines": int}``.
        Only ``name`` is required.
        """
        estimates: list[StepEstimate] = []
        for step in steps:
            est = self.estimate_step(
                description=step["name"],
                context_files=step.get("context_files", 0),
                expected_output_lines=step.get("output_lines", 0),
            )
            estimates.append(est)

        total_input = sum(e.estimated_input_tokens for e in estimates)
        total_output = sum(e.estimated_output_tokens for e in estimates)
        total_cost = sum(e.estimated_cost_usd for e in estimates)
        total_seconds = sum(e.estimated_seconds for e in estimates)
        avg_confidence = (
            sum(e.confidence for e in estimates) / len(estimates)
            if estimates
            else 0.0
        )

        return CostProjection(
            steps=estimates,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost,
            total_seconds=total_seconds,
            model=self.model,
            confidence=avg_confidence,
        )

    def record_actual(
        self,
        step_name: str,
        input_tokens: int,
        output_tokens: int,
        elapsed: float,
    ) -> None:
        """Record actual usage for a step (keeps last 10 samples)."""
        entry = self._history.setdefault(step_name, {"samples": []})
        samples = entry["samples"]
        samples.append({
            "input": input_tokens,
            "output": output_tokens,
            "elapsed": elapsed,
        })
        # Keep only last 10
        if len(samples) > 10:
            entry["samples"] = samples[-10:]
        self._save_history()

    def accuracy_report(self) -> str:
        """Compare heuristic projections vs actual averages from history."""
        if not self._history:
            return "No historical data available."

        lines: list[str] = ["Accuracy Report", "=" * 60]
        for step_name, entry in self._history.items():
            samples = entry.get("samples", [])
            if not samples:
                continue
            avg_input = sum(s["input"] for s in samples) / len(samples)
            avg_output = sum(s["output"] for s in samples) / len(samples)

            # Heuristic estimate for comparison
            heuristic = self.estimate_step(step_name)
            # Since estimate_step uses history when available, compute
            # the raw heuristic manually for comparison
            word_count = len(step_name.split())
            heur_input = self.BASE_INPUT_TOKENS + word_count * 2
            heur_output = self.DEFAULT_OUTPUT_TOKENS

            input_dev = (
                ((avg_input - heur_input) / heur_input * 100) if heur_input else 0
            )
            output_dev = (
                ((avg_output - heur_output) / heur_output * 100)
                if heur_output
                else 0
            )
            lines.append(
                f"{step_name}: input deviation {input_dev:+.1f}%, "
                f"output deviation {output_dev:+.1f}% "
                f"({len(samples)} samples)"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_history(self) -> dict:
        """Load JSON history from disk. Returns ``{}`` on any error."""
        if self.history_path is None:
            return {}
        try:
            text = self.history_path.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            return {}
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _save_history(self) -> None:
        """Persist history to disk. No-op when *history_path* is ``None``."""
        if self.history_path is None:
            return
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self._history, indent=2),
                encoding="utf-8",
            )
        except OSError:
            logger.warning("Failed to save cost projector history to %s", self.history_path)

    def _get_pricing(self) -> ModelPricing:
        """Resolve pricing for *self.model*.

        1. Exact match in ``self.pricing``.
        2. Prefix match (e.g. ``"claude-sonnet"`` matches ``"claude-sonnet-4"``).
        3. Fallback to ``gpt-4o`` pricing.
        """
        # Exact match
        if self.model in self.pricing:
            return self.pricing[self.model]

        # Prefix match — model arg is a prefix of a key
        for key, val in self.pricing.items():
            if key.startswith(self.model):
                return val

        # Reverse prefix — key is a prefix of model arg
        for key, val in self.pricing.items():
            if self.model.startswith(key):
                return val

        # Fallback
        if "gpt-4o" in self.pricing:
            return self.pricing["gpt-4o"]

        # Last resort: return first available pricing
        if self.pricing:
            return next(iter(self.pricing.values()))

        return ModelPricing("unknown", 0.0025, 0.01, 50.0)
