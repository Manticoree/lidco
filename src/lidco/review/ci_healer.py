"""Self-healing CI/CD loop — watches failures, fixes, re-runs, reports (Windsurf/Dagger parity)."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class CIFailure:
    step: str       # e.g. "pytest", "ruff", "mypy"
    output: str     # raw failure text
    files: list[str] = field(default_factory=list)   # affected file paths


@dataclass
class HealIteration:
    attempt: int
    failures_found: int
    fixes_applied: int
    passed: bool
    summary: str


@dataclass
class HealResult:
    success: bool
    attempts: int
    history: list[HealIteration] = field(default_factory=list)
    final_output: str = ""

    def format_report(self) -> str:
        status = "HEALED" if self.success else "FAILED"
        lines = [f"CI Heal [{status}] after {self.attempts} attempt(s)"]
        for h in self.history:
            icon = "+" if h.passed else "-"
            lines.append(f"  [{icon}] attempt {h.attempt}: {h.summary}")
        return "\n".join(lines)


# Known failure patterns → fixer hints
_FAILURE_PATTERNS: list[tuple[str, str, str]] = [
    # (step_name, regex_to_detect, hint)
    ("pytest", r"FAILED|ERROR|assert.*==", "pytest"),
    ("ruff", r"ruff.*error|Found \d+ error", "ruff"),
    ("mypy", r"error:.*\[", "mypy"),
    ("flake8", r"E\d{3}|W\d{3}", "flake8"),
    ("black", r"would reformat|reformatted", "black"),
]


def _parse_failures(output: str) -> list[CIFailure]:
    failures: list[CIFailure] = []
    for step, pattern, name in _FAILURE_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            # Extract file references
            files = list(dict.fromkeys(re.findall(r'[\w/.\-]+\.py', output)))[:10]
            failures.append(CIFailure(step=name, output=output[:1000], files=files))
    if not failures and output.strip():
        failures.append(CIFailure(step="unknown", output=output[:500], files=[]))
    return failures


class CIPipelineHealer:
    """Run a CI command, detect failures, apply fixes, retry up to max_attempts.

    The fixer_callback(failures) -> dict[str, str] returns file patches.
    If fixer_callback is None, reports failures without fixing.
    """

    def __init__(
        self,
        fixer_callback: Callable[[list[CIFailure]], Awaitable[dict[str, str]]] | None = None,
        max_attempts: int = 3,
        cwd: str = ".",
    ) -> None:
        self._fixer = fixer_callback
        self.max_attempts = max_attempts
        self.cwd = cwd

    def _run(self, command: str) -> tuple[int, str]:
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=120, cwd=self.cwd,
            )
            return r.returncode, (r.stdout + "\n" + r.stderr).strip()
        except subprocess.TimeoutExpired:
            return 1, "Command timed out"
        except Exception as e:
            return 1, str(e)

    def _apply_patches(self, patches: dict[str, str]) -> int:
        from pathlib import Path
        applied = 0
        for path_str, content in patches.items():
            try:
                p = Path(path_str)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                applied += 1
            except OSError:
                pass
        return applied

    async def heal(self, command: str) -> HealResult:
        history: list[HealIteration] = []
        for attempt in range(1, self.max_attempts + 1):
            rc, output = self._run(command)
            if rc == 0:
                history.append(HealIteration(
                    attempt=attempt, failures_found=0, fixes_applied=0,
                    passed=True, summary="All checks passed",
                ))
                return HealResult(success=True, attempts=attempt, history=history, final_output=output)

            failures = _parse_failures(output)
            fixes_applied = 0
            if self._fixer is not None:
                try:
                    patches = await self._fixer(failures)
                    fixes_applied = self._apply_patches(patches)
                except Exception as e:
                    history.append(HealIteration(
                        attempt=attempt, failures_found=len(failures),
                        fixes_applied=0, passed=False,
                        summary=f"fixer error: {e}",
                    ))
                    break
            history.append(HealIteration(
                attempt=attempt, failures_found=len(failures),
                fixes_applied=fixes_applied, passed=False,
                summary=f"{len(failures)} failure(s), {fixes_applied} fix(es) applied",
            ))
            if self._fixer is None:
                break

        last_output = history[-1].summary if history else ""
        return HealResult(success=False, attempts=len(history), history=history, final_output=last_output)
