"""Docker sandbox tool — run commands inside an isolated Docker container."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


@dataclass(frozen=True)
class SandboxResult:
    """Result from a Docker sandbox execution."""

    stdout: str
    stderr: str
    returncode: int
    elapsed: float


class DockerSandbox:
    """Execute commands inside a Docker container for isolation."""

    def __init__(self, image: str = "python:3.12-slim") -> None:
        self.image = image

    def is_available(self) -> bool:
        """Return True if the `docker` binary is in PATH."""
        return shutil.which("docker") is not None

    def run(self, command: str, timeout: int = 60) -> SandboxResult:
        """Run *command* inside the Docker image, returning captured output."""
        if not self.is_available():
            return SandboxResult(
                stdout="",
                stderr="docker not found in PATH",
                returncode=127,
                elapsed=0.0,
            )

        cmd = [
            "docker", "run", "--rm", "-i",
            "--network", "none",
            self.image,
            "bash", "-c", command,
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.monotonic() - start
            return SandboxResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                elapsed=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return SandboxResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                returncode=124,
                elapsed=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            return SandboxResult(
                stdout="",
                stderr="docker not found in PATH",
                returncode=127,
                elapsed=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return SandboxResult(
                stdout="",
                stderr=str(exc),
                returncode=1,
                elapsed=elapsed,
            )


class DockerSandboxTool(BaseTool):
    """Tool: run a command inside a Docker sandbox container."""

    @property
    def name(self) -> str:
        return "docker_sandbox"

    @property
    def description(self) -> str:
        return (
            "Run a shell command inside an isolated Docker container with no network access. "
            "Useful for safely executing untrusted code."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to execute inside the container",
            ),
            ToolParameter(
                name="image",
                type="string",
                description="Docker image to use (default: python:3.12-slim)",
                required=False,
                default="python:3.12-slim",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Execution timeout in seconds (default 60)",
                required=False,
                default=60,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        image = kwargs.get("image", "python:3.12-slim")
        timeout = int(kwargs.get("timeout", 60))

        sandbox = DockerSandbox(image=image)

        if not sandbox.is_available():
            return ToolResult(
                output="Docker is not available. Install Docker to use this tool.",
                success=False,
                error="docker not found",
            )

        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: sandbox.run(command, timeout)
        )

        parts = []
        if result.stdout:
            parts.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            parts.append(f"STDERR:\n{result.stderr}")
        parts.append(f"Exit code: {result.returncode} | Elapsed: {result.elapsed:.2f}s")
        output = "\n".join(parts)
        return ToolResult(output=output, success=(result.returncode == 0))
