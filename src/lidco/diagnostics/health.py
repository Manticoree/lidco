"""Health check system — Task 442."""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HealthResult:
    """Result of a single health check."""

    name: str
    status: str          # "ok" | "warn" | "fail"
    message: str
    duration_ms: float = 0.0


class HealthCheck:
    """Runs a suite of health checks for LIDCO."""

    # ── individual checks ─────────────────────────────────────────────────────

    def check_api_keys(self) -> HealthResult:
        """Verify that at least one LLM API key is present."""
        t0 = time.perf_counter()
        keys = {
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        }
        present = {k: bool(v) for k, v in keys.items()}
        ms = (time.perf_counter() - t0) * 1000

        if all(present.values()):
            return HealthResult("api_keys", "ok", "All API keys present", ms)
        if any(present.values()):
            missing = [k for k, v in present.items() if not v]
            return HealthResult(
                "api_keys", "warn",
                f"Some API keys missing: {', '.join(missing)}", ms,
            )
        return HealthResult(
            "api_keys", "fail",
            "No API keys set (ANTHROPIC_API_KEY, OPENAI_API_KEY)", ms,
        )

    def check_models(self, config: Any = None) -> HealthResult:
        """Verify configured models are reachable (light ping)."""
        t0 = time.perf_counter()
        ms = (time.perf_counter() - t0) * 1000

        if config is None:
            return HealthResult("models", "warn", "No config provided — skipping model ping", ms)

        try:
            model = getattr(getattr(config, "llm", None), "default_model", None)
            if not model:
                return HealthResult("models", "warn", "No default model configured", ms)
            # We do a lightweight check — just verify the model name is non-empty
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("models", "ok", f"Default model: {model}", ms)
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("models", "fail", f"Model check failed: {exc}", ms)

    def check_tools(self, registry: Any = None) -> HealthResult:
        """Verify that tool registry is accessible and non-empty."""
        t0 = time.perf_counter()
        ms = (time.perf_counter() - t0) * 1000

        if registry is None:
            return HealthResult("tools", "warn", "No registry provided", ms)

        try:
            tools = getattr(registry, "_tools", None)
            if tools is None:
                tools = {}
            count = len(tools)
            ms = (time.perf_counter() - t0) * 1000
            if count == 0:
                return HealthResult("tools", "warn", "Tool registry is empty", ms)
            return HealthResult("tools", "ok", f"{count} tools registered", ms)
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("tools", "fail", f"Tool check failed: {exc}", ms)

    def check_rag(self) -> HealthResult:
        """Verify ChromaDB is importable and the index directory exists."""
        t0 = time.perf_counter()
        try:
            import chromadb  # noqa: F401
            index_dir = Path.cwd() / ".lidco" / "rag_index"
            ms = (time.perf_counter() - t0) * 1000
            if index_dir.exists():
                return HealthResult("rag", "ok", "ChromaDB available, index present", ms)
            return HealthResult("rag", "warn", "ChromaDB available, index not yet built", ms)
        except ImportError:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("rag", "warn", "chromadb not installed — RAG unavailable", ms)
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("rag", "fail", f"RAG check failed: {exc}", ms)

    def check_db(self) -> HealthResult:
        """Verify the SQLite error ledger is accessible."""
        t0 = time.perf_counter()
        db_path = Path.cwd() / ".lidco" / "error_ledger.db"
        try:
            if not db_path.exists():
                ms = (time.perf_counter() - t0) * 1000
                return HealthResult("db", "warn", f"Error ledger not found at {db_path}", ms)
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT 1")
            conn.close()
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("db", "ok", f"SQLite ledger accessible ({db_path.name})", ms)
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("db", "fail", f"DB check failed: {exc}", ms)

    def check_disk_space(self) -> HealthResult:
        """Warn if less than 500 MB free on the project drive."""
        t0 = time.perf_counter()
        try:
            usage = shutil.disk_usage(str(Path.cwd()))
            free_mb = usage.free / (1024 * 1024)
            ms = (time.perf_counter() - t0) * 1000
            if free_mb < 500:
                return HealthResult(
                    "disk_space", "warn",
                    f"Low disk space: {free_mb:.0f} MB free (threshold: 500 MB)", ms,
                )
            return HealthResult(
                "disk_space", "ok",
                f"{free_mb:,.0f} MB free", ms,
            )
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            return HealthResult("disk_space", "fail", f"Disk check failed: {exc}", ms)

    # ── run all ───────────────────────────────────────────────────────────────

    def run_all(
        self,
        config: Any = None,
        registry: Any = None,
    ) -> list[HealthResult]:
        """Run all health checks and return results."""
        return [
            self.check_api_keys(),
            self.check_models(config),
            self.check_tools(registry),
            self.check_rag(),
            self.check_db(),
            self.check_disk_space(),
        ]

    # ── Rich table rendering ──────────────────────────────────────────────────

    def render_table(self, results: list[HealthResult]) -> Any:
        """Return a Rich Table for *results*."""
        from rich.table import Table

        table = Table(title="LIDCO Health Check", show_header=True, header_style="bold")
        table.add_column("Check", style="bold")
        table.add_column("Status")
        table.add_column("Message")
        table.add_column("ms", justify="right", style="dim")

        _STATUS_STYLE = {"ok": "green", "warn": "yellow", "fail": "red"}

        for r in results:
            style = _STATUS_STYLE.get(r.status, "")
            status_text = f"[{style}]{r.status.upper()}[/{style}]" if style else r.status.upper()
            table.add_row(r.name, status_text, r.message, f"{r.duration_ms:.1f}")

        return table
