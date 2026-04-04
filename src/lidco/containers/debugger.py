"""ContainerDebugger — debug containers via subprocess wrappers (stdlib only)."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class HealthResult:
    """Result of a container health check."""

    container_id: str
    running: bool
    status: str
    health: str  # "healthy", "unhealthy", "none", "unknown"
    ports: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ContainerDebugger:
    """Debug running containers — logs, exec, port-forward, health checks.

    Accepts an optional *run_fn* for executing shell commands so that tests
    can inject a mock instead of shelling out to docker/kubectl.
    """

    def __init__(
        self,
        run_fn: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self._run = run_fn or self._default_run

    # ------------------------------------------------------------------ #
    # Internal runner                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _default_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def logs(self, container_id: str, *, tail: int = 100) -> list[str]:
        """Return recent log lines from *container_id*."""
        if not container_id:
            raise ValueError("container_id must not be empty")
        result = self._run(["docker", "logs", "--tail", str(tail), container_id])
        output = result.stdout or result.stderr or ""
        return [line for line in output.splitlines() if line.strip()]

    def exec_cmd(self, container_id: str, cmd: str) -> str:
        """Execute *cmd* inside a running container and return stdout."""
        if not container_id:
            raise ValueError("container_id must not be empty")
        if not cmd:
            raise ValueError("cmd must not be empty")
        result = self._run(["docker", "exec", container_id] + cmd.split())
        if result.returncode != 0:
            err = result.stderr.strip() if result.stderr else f"exit code {result.returncode}"
            raise RuntimeError(f"Command failed in {container_id}: {err}")
        return result.stdout.strip()

    def port_forward(
        self,
        container: str,
        local_port: int,
        remote_port: int,
    ) -> dict[str, Any]:
        """Return a port-forward configuration dict (does not actually bind).

        In a real deployment this would start a background process; here it
        returns the config so callers can act on it.
        """
        if local_port < 1 or local_port > 65535:
            raise ValueError(f"Invalid local port: {local_port}")
        if remote_port < 1 or remote_port > 65535:
            raise ValueError(f"Invalid remote port: {remote_port}")
        return {
            "container": container,
            "local_port": local_port,
            "remote_port": remote_port,
            "status": "configured",
            "command": f"docker exec -d {container} socat TCP-LISTEN:{remote_port},fork TCP:localhost:{remote_port}",
        }

    def health_check(self, container_id: str) -> dict[str, Any]:
        """Inspect container health and return a status dict."""
        if not container_id:
            raise ValueError("container_id must not be empty")
        result = self._run(
            ["docker", "inspect", "--format", "{{json .State}}", container_id]
        )
        if result.returncode != 0:
            return HealthResult(
                container_id=container_id,
                running=False,
                status="not_found",
                health="unknown",
                errors=[result.stderr.strip() if result.stderr else "inspect failed"],
            ).__dict__

        try:
            state = json.loads(result.stdout.strip())
        except (json.JSONDecodeError, TypeError):
            state = {}

        running = state.get("Running", False)
        status = state.get("Status", "unknown")
        health_obj = state.get("Health", {})
        health_status = health_obj.get("Status", "none") if isinstance(health_obj, dict) else "none"

        return HealthResult(
            container_id=container_id,
            running=running,
            status=status,
            health=health_status,
        ).__dict__
