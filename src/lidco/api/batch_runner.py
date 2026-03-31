"""Batch prompt runner — execute multiple prompts sequentially or in parallel — Q171."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from lidco.api.library import LidcoResult


@dataclass
class BatchJob:
    """Single job in a batch run."""

    prompt: str
    index: int
    result: LidcoResult | None = None


class BatchRunner:
    """Execute a list of prompts and collect results."""

    def __init__(
        self,
        execute_fn: Callable[[str], LidcoResult],
        max_parallel: int = 1,
    ) -> None:
        self._execute_fn = execute_fn
        self._max_parallel = max(1, max_parallel)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_prompts(source: str) -> list[str]:
        """Load prompts from a file path.

        Supports:
        - JSON array (``["prompt1", "prompt2"]``)
        - Plain text, one prompt per line
        """
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        stripped = text.strip()
        if stripped.startswith("["):
            try:
                data = json.loads(stripped)
                if isinstance(data, list):
                    return [str(item) for item in data if str(item).strip()]
            except json.JSONDecodeError:
                pass
        # Plain text: one prompt per line
        return [line for line in text.splitlines() if line.strip()]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_all(self, prompts: list[str]) -> list[BatchJob]:
        """Execute all prompts (sequential for now) and collect results."""
        return self.run_sequential(prompts)

    def run_sequential(self, prompts: list[str]) -> list[BatchJob]:
        """Execute prompts one-by-one in order."""
        jobs: list[BatchJob] = []
        for idx, prompt in enumerate(prompts):
            job = BatchJob(prompt=prompt, index=idx)
            job.result = self._execute_fn(prompt)
            jobs.append(job)
        return jobs

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def summary(jobs: list[BatchJob]) -> dict:
        """Return aggregated summary of batch results."""
        success = sum(1 for j in jobs if j.result and j.result.success)
        fail = sum(1 for j in jobs if j.result and not j.result.success)
        total_time = sum(j.result.duration for j in jobs if j.result)
        total_tokens = sum(j.result.tokens_used for j in jobs if j.result)
        return {
            "total": len(jobs),
            "success": success,
            "fail": fail,
            "total_time": round(total_time, 4),
            "total_tokens": total_tokens,
        }

    @staticmethod
    def to_json(jobs: list[BatchJob]) -> str:
        """Serialize batch results to JSON."""
        entries = []
        for j in jobs:
            entry: dict = {"index": j.index, "prompt": j.prompt}
            if j.result is not None:
                entry["success"] = j.result.success
                entry["output"] = j.result.output
                entry["tokens_used"] = j.result.tokens_used
                entry["duration"] = j.result.duration
                entry["error"] = j.result.error
            entries.append(entry)
        return json.dumps(entries, indent=2)
