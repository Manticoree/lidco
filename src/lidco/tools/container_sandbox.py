"""ContainerSandbox — Docker-backed isolated task execution (Devin/Jules parity)."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContainerConfig:
    image: str = "python:3.13-slim"
    repo_path: str = "."
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 120.0
    network_disabled: bool = True
    memory_limit_mb: int = 512


@dataclass
class ContainerResult:
    exit_code: int
    stdout: str
    stderr: str
    diff: str
    duration: float


class ContainerSandbox:
    """Run commands in an isolated Docker container and capture the git diff."""

    def __init__(self, config: ContainerConfig | None = None) -> None:
        self._config = config or ContainerConfig()
        self._container_id: str | None = None

    # ------------------------------------------------------------------
    # Docker availability check
    # ------------------------------------------------------------------

    @staticmethod
    def _docker_available() -> bool:
        try:
            r = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, command: str) -> ContainerResult:
        """Execute command in a Docker container. Falls back gracefully."""
        if not self._docker_available():
            return ContainerResult(
                exit_code=1,
                stdout="",
                stderr="Docker not available",
                diff="",
                duration=0.0,
            )

        repo_path = str(Path(self._config.repo_path).resolve())
        docker_args = [
            "docker", "run",
            "--rm",
            "-v", f"{repo_path}:/workspace",
            "-w", "/workspace",
        ]

        if self._config.network_disabled:
            docker_args += ["--network", "none"]

        if self._config.memory_limit_mb:
            docker_args += [f"--memory={self._config.memory_limit_mb}m"]

        for key, val in self._config.env.items():
            docker_args += ["-e", f"{key}={val}"]

        docker_args += [self._config.image, "sh", "-c", command]

        start = time.monotonic()
        try:
            result = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=self._config.timeout,
            )
            duration = time.monotonic() - start
            diff = self.get_diff()
            return ContainerResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                diff=diff,
                duration=duration,
            )
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return ContainerResult(
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {self._config.timeout}s",
                diff="",
                duration=duration,
            )
        except Exception as exc:
            return ContainerResult(
                exit_code=1,
                stdout="",
                stderr=str(exc),
                diff="",
                duration=0.0,
            )

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def get_diff(self) -> str:
        """Run git diff in repo_path to capture changes from sandbox execution."""
        repo_path = str(Path(self._config.repo_path).resolve())
        try:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            return result.stdout
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Stop and remove any running container (no-op for --rm containers)."""
        if self._container_id:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self._container_id],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass
            self._container_id = None
