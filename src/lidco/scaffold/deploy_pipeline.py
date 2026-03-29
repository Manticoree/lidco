"""DeployPipeline — orchestrate build+deploy steps with dry-run and rollback (stdlib only)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from lidco.scaffold.deploy_registry import DeployProvider


@dataclass
class DeployJob:
    """Tracks a single deploy execution."""

    job_id: str = ""
    provider: Optional[DeployProvider] = None
    project_dir: str = ""
    env: dict = field(default_factory=dict)
    branch: str = "main"
    dry_run: bool = False

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = uuid.uuid4().hex


@dataclass
class DeployResult:
    """Outcome of a deploy pipeline run."""

    job_id: str = ""
    success: bool = False
    url: str = ""
    duration_ms: int = 0
    logs: list[str] = field(default_factory=list)
    error: str = ""


class DeployPipeline:
    """Orchestrates build and deploy steps for a provider."""

    def __init__(
        self,
        job_queue: Any = None,
        checkpoint_manager: Any = None,
    ) -> None:
        self._job_queue = job_queue
        self._checkpoint_manager = checkpoint_manager

    def run(
        self,
        project_dir: str,
        provider: DeployProvider,
        env: dict | None = None,
        branch: str = "main",
        dry_run: bool = False,
    ) -> DeployResult:
        """Run the build+deploy pipeline. Returns DeployResult (always non-empty logs)."""
        job = DeployJob(
            provider=provider,
            project_dir=project_dir,
            env=env or {},
            branch=branch,
            dry_run=dry_run,
        )

        start = time.monotonic()
        logs: list[str] = [f"Starting deploy for {provider.name} (branch={branch})"]

        # Build step
        ok, msg = self._run_step("build", provider.build_cmd, dry_run)
        logs.append(f"[build] {msg}")
        if not ok:
            elapsed = int((time.monotonic() - start) * 1000)
            if self._checkpoint_manager is not None:
                try:
                    self._checkpoint_manager.rollback()
                except Exception:
                    logs.append("[rollback] checkpoint rollback failed")
            return DeployResult(
                job_id=job.job_id,
                success=False,
                url="",
                duration_ms=elapsed,
                logs=logs,
                error=msg,
            )

        # Deploy step
        ok, msg = self._run_step("deploy", provider.deploy_cmd, dry_run)
        logs.append(f"[deploy] {msg}")
        if not ok:
            elapsed = int((time.monotonic() - start) * 1000)
            if self._checkpoint_manager is not None:
                try:
                    self._checkpoint_manager.rollback()
                except Exception:
                    logs.append("[rollback] checkpoint rollback failed")
            return DeployResult(
                job_id=job.job_id,
                success=False,
                url="",
                duration_ms=elapsed,
                logs=logs,
                error=msg,
            )

        elapsed = int((time.monotonic() - start) * 1000)
        url = f"https://{provider.name}.app/{branch}" if not dry_run else ""
        logs.append("Deploy complete.")
        return DeployResult(
            job_id=job.job_id,
            success=True,
            url=url,
            duration_ms=elapsed,
            logs=logs,
        )

    def _run_step(self, step_name: str, cmd: str, dry_run: bool) -> tuple[bool, str]:
        """Execute a single pipeline step. Returns (success, message)."""
        if dry_run:
            return True, f"dry-run: would execute '{cmd}'"
        # Simulate success in non-dry-run (no real subprocess)
        return True, f"executed '{cmd}' successfully"

    def estimate(self, provider: DeployProvider) -> dict:
        """Return estimated steps and duration."""
        steps = ["build", "deploy"]
        return {
            "steps": steps,
            "estimated_duration_ms": len(steps) * 30_000,
        }
