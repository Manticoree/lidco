"""ModelBenchmark — track and rank model performance."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkResult:
    """Performance snapshot for one model."""

    model: str
    latency_ms: float
    quality_score: float
    cost_estimate: float
    rank: int = 0


class ModelBenchmark:
    """Collect benchmark results and produce rankings."""

    def __init__(self) -> None:
        self._results: list[BenchmarkResult] = []

    def add_result(self, result: BenchmarkResult) -> None:
        self._results = [*self._results, result]

    def ranking(self) -> list[BenchmarkResult]:
        """Return results sorted by quality desc, then latency asc, with ranks."""
        ordered = sorted(
            self._results, key=lambda r: (-r.quality_score, r.latency_ms)
        )
        return [
            BenchmarkResult(
                model=r.model,
                latency_ms=r.latency_ms,
                quality_score=r.quality_score,
                cost_estimate=r.cost_estimate,
                rank=i + 1,
            )
            for i, r in enumerate(ordered)
        ]

    def compare(self, model_a: str, model_b: str) -> dict:
        """Side-by-side comparison of two models."""
        a = next((r for r in self._results if r.model == model_a), None)
        b = next((r for r in self._results if r.model == model_b), None)
        return {
            "model_a": a.model if a else model_a,
            "model_b": b.model if b else model_b,
            "latency_diff_ms": (a.latency_ms - b.latency_ms) if a and b else 0.0,
            "quality_diff": (a.quality_score - b.quality_score) if a and b else 0.0,
            "cost_diff": (a.cost_estimate - b.cost_estimate) if a and b else 0.0,
            "winner": self._pick_winner(a, b),
        }

    def summary(self) -> str:
        ranked = self.ranking()
        if not ranked:
            return "No benchmark results."
        lines = [f"{len(ranked)} model(s) benchmarked:"]
        for r in ranked:
            lines.append(
                f"  #{r.rank} {r.model} — quality={r.quality_score:.1f} "
                f"latency={r.latency_ms:.0f}ms cost=${r.cost_estimate:.4f}"
            )
        return "\n".join(lines)

    def best(self) -> BenchmarkResult | None:
        ranked = self.ranking()
        return ranked[0] if ranked else None

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _pick_winner(
        a: BenchmarkResult | None, b: BenchmarkResult | None
    ) -> str:
        if a is None and b is None:
            return ""
        if a is None:
            return b.model  # type: ignore[union-attr]
        if b is None:
            return a.model
        if a.quality_score > b.quality_score:
            return a.model
        if b.quality_score > a.quality_score:
            return b.model
        # tie-break on latency
        return a.model if a.latency_ms <= b.latency_ms else b.model
