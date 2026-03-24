"""Auto-lint and auto-test fix loop — runs checks, asks LLM to fix, repeats."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable


@dataclass
class FixIteration:
    iteration: int
    command: str
    returncode: int
    stdout: str
    stderr: str
    fixed: bool   # True if the check passed this iteration


@dataclass
class AutoFixResult:
    success: bool
    iterations: int
    history: list[FixIteration] = field(default_factory=list)
    final_output: str = ""


class AutoFixer:
    """Run a shell command (linter/test suite), pass failures to an LLM fixer, repeat.

    The fixer_callback receives (failure_output: str, file_contents: dict[str, str])
    and returns a dict of {path: new_content} patches to apply.
    """

    def __init__(
        self,
        fixer_callback: Callable[[str, dict[str, str]], Awaitable[dict[str, str]]] | None = None,
        max_iterations: int = 5,
        cwd: str | None = None,
    ) -> None:
        self._fixer = fixer_callback
        self.max_iterations = max_iterations
        self.cwd = cwd or "."

    def _run_command(self, command: str) -> tuple[int, str, str]:
        """Run shell command, return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.cwd,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    def _read_files(self, paths: list[str]) -> dict[str, str]:
        """Read file contents for LLM context."""
        contents: dict[str, str] = {}
        for p in paths:
            try:
                contents[p] = Path(p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return contents

    def _apply_patches(self, patches: dict[str, str]) -> None:
        """Write patched file contents."""
        for path, content in patches.items():
            try:
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            except OSError:
                pass

    async def run(
        self,
        command: str,
        files_to_fix: list[str] | None = None,
    ) -> AutoFixResult:
        """Run command and fix failures up to max_iterations.

        Args:
            command: Shell command to run (e.g. "python -m pytest tests/ -q" or "ruff check src/").
            files_to_fix: Paths to include in LLM context when fixing.
        """
        history: list[FixIteration] = []
        files = files_to_fix or []

        for i in range(1, self.max_iterations + 1):
            rc, stdout, stderr = self._run_command(command)
            output = (stdout + "\n" + stderr).strip()
            passed = rc == 0

            history.append(FixIteration(
                iteration=i,
                command=command,
                returncode=rc,
                stdout=stdout,
                stderr=stderr,
                fixed=passed,
            ))

            if passed:
                return AutoFixResult(success=True, iterations=i, history=history, final_output=output)

            if self._fixer is None:
                # No fixer — just report the failure
                break

            # Ask LLM to fix
            file_contents = self._read_files(files)
            try:
                patches = await self._fixer(output, file_contents)
                if patches:
                    self._apply_patches(patches)
            except Exception:
                break

        last = history[-1] if history else None
        return AutoFixResult(
            success=False,
            iterations=len(history),
            history=history,
            final_output=(last.stdout + "\n" + last.stderr).strip() if last else "",
        )

    def run_sync(self, command: str, files_to_fix: list[str] | None = None) -> "FixIteration":
        """Run command once (no LLM fix loop) and return a single FixIteration."""
        rc, stdout, stderr = self._run_command(command)
        return FixIteration(
            iteration=1,
            command=command,
            returncode=rc,
            stdout=stdout,
            stderr=stderr,
            fixed=rc == 0,
        )
