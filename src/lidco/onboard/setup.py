"""Setup Assistant — guided dev environment setup with dependency check,
config generation, first build, and verification.

Part of Q330 — Onboarding Intelligence (task 1764).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence


class CheckStatus(Enum):
    """Status of a setup check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single setup check."""

    name: str
    status: CheckStatus
    message: str = ""
    fix_hint: str = ""


@dataclass(frozen=True)
class SetupStep:
    """A step in the setup process."""

    name: str
    description: str
    command: str = ""
    check_command: str = ""
    required: bool = True
    order: int = 0


@dataclass
class SetupReport:
    """Overall setup report."""

    results: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.FAIL)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARN)

    @property
    def all_passed(self) -> bool:
        return all(r.status != CheckStatus.FAIL for r in self.results)


class SetupAssistant:
    """Guided dev environment setup with dependency checks, config gen, and verification."""

    def __init__(self, root_dir: str = ".") -> None:
        self._root_dir = root_dir
        self._steps: List[SetupStep] = []
        self._checks: Dict[str, Callable[[], CheckResult]] = {}
        self._config_templates: Dict[str, str] = {}

    @property
    def root_dir(self) -> str:
        return self._root_dir

    @property
    def steps(self) -> List[SetupStep]:
        return list(self._steps)

    def add_step(self, step: SetupStep) -> None:
        """Add a setup step."""
        self._steps = [*self._steps, step]

    def add_steps(self, steps: Sequence[SetupStep]) -> None:
        """Add multiple setup steps."""
        for s in steps:
            self.add_step(s)

    def register_check(self, name: str, check_fn: Callable[[], CheckResult]) -> None:
        """Register a named dependency check."""
        self._checks = {**self._checks, name: check_fn}

    def check_dependency(self, name: str) -> CheckResult:
        """Run a specific registered check."""
        fn = self._checks.get(name)
        if fn is None:
            return CheckResult(name=name, status=CheckStatus.SKIP, message="No check registered")
        try:
            return fn()
        except Exception as exc:
            return CheckResult(name=name, status=CheckStatus.FAIL, message=str(exc))

    def check_command_exists(self, command: str) -> CheckResult:
        """Check if a command is available on PATH."""
        found = shutil.which(command)
        if found:
            return CheckResult(
                name=command,
                status=CheckStatus.PASS,
                message=f"Found: {found}",
            )
        return CheckResult(
            name=command,
            status=CheckStatus.FAIL,
            message=f"'{command}' not found on PATH",
            fix_hint=f"Install '{command}' and ensure it is on your PATH.",
        )

    def check_file_exists(self, path: str) -> CheckResult:
        """Check if a file exists relative to root_dir."""
        full = os.path.join(self._root_dir, path)
        if os.path.isfile(full):
            return CheckResult(name=path, status=CheckStatus.PASS, message="File exists")
        return CheckResult(
            name=path,
            status=CheckStatus.FAIL,
            message=f"File not found: {path}",
            fix_hint=f"Create '{path}' or run config generation.",
        )

    def check_python_version(self, min_version: str = "3.10") -> CheckResult:
        """Check Python version is at least min_version."""
        import sys

        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        if tuple(int(x) for x in current.split(".")) >= tuple(
            int(x) for x in min_version.split(".")
        ):
            return CheckResult(
                name="python",
                status=CheckStatus.PASS,
                message=f"Python {current} >= {min_version}",
            )
        return CheckResult(
            name="python",
            status=CheckStatus.FAIL,
            message=f"Python {current} < {min_version}",
            fix_hint=f"Upgrade to Python {min_version}+",
        )

    def run_all_checks(self) -> SetupReport:
        """Run all registered checks and return a report."""
        results: List[CheckResult] = []
        for name, fn in sorted(self._checks.items()):
            results = [*results, self.check_dependency(name)]
        return SetupReport(results=results)

    def add_config_template(self, name: str, content: str) -> None:
        """Register a config template for generation."""
        self._config_templates = {**self._config_templates, name: content}

    def generate_config(self, name: str, variables: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Generate config content from a template with variable substitution."""
        template = self._config_templates.get(name)
        if template is None:
            return None
        result = template
        for key, val in (variables or {}).items():
            result = result.replace(f"{{{{{key}}}}}", val)
        return result

    def list_config_templates(self) -> List[str]:
        """Return names of available config templates."""
        return sorted(self._config_templates.keys())

    def verify_setup(self) -> SetupReport:
        """Verify the full setup by running all checks and step verifications."""
        report = self.run_all_checks()
        step_results: List[CheckResult] = list(report.results)
        for step in sorted(self._steps, key=lambda s: s.order):
            if step.check_command:
                found = shutil.which(step.check_command.split()[0])
                status = CheckStatus.PASS if found else CheckStatus.FAIL
                step_results = [
                    *step_results,
                    CheckResult(
                        name=f"step:{step.name}",
                        status=status,
                        message=f"{'OK' if found else 'Not available'}: {step.check_command}",
                    ),
                ]
        return SetupReport(results=step_results)

    def summary(self) -> str:
        """Return a human-readable summary."""
        report = self.verify_setup()
        lines = [
            f"Setup Assistant: {self._root_dir}",
            f"Steps: {len(self._steps)}",
            f"Checks: {len(self._checks)}",
            f"Config templates: {len(self._config_templates)}",
            f"Results: {report.passed} passed, {report.failed} failed, {report.warnings} warnings",
        ]
        if report.all_passed:
            lines.append("Status: READY")
        else:
            lines.append("Status: NEEDS ATTENTION")
            for r in report.results:
                if r.status == CheckStatus.FAIL:
                    lines.append(f"  FAIL: {r.name} — {r.message}")
                    if r.fix_hint:
                        lines.append(f"    Fix: {r.fix_hint}")
        return "\n".join(lines)
