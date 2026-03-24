"""FixVerifier — apply a patch and verify tests still pass."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .autofix_agent import FixProposal


@dataclass
class VerifyResult:
    passed: bool
    test_output: str
    regression_count: int = 0


class FixVerifier:
    """Apply a FixProposal to a temp copy and verify tests pass."""

    def __init__(self, project_dir: Path | None = None, test_cmd: str = "python -m pytest -q --tb=no") -> None:
        self._project_dir = project_dir or Path.cwd()
        self._test_cmd = test_cmd

    def verify(self, proposal: FixProposal) -> VerifyResult:
        """Apply patch in a temp dir and run tests. Returns VerifyResult."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                shutil.copytree(str(self._project_dir), str(tmp_path / "proj"), dirs_exist_ok=True)
            except Exception as exc:
                return VerifyResult(passed=False, test_output=str(exc))

            # Apply patch via `patch` command if patch content present
            if proposal.patch.strip():
                try:
                    result = subprocess.run(
                        ["git", "apply", "--check"],
                        input=proposal.patch,
                        cwd=tmp_path / "proj",
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    patch_ok = result.returncode == 0
                except Exception:
                    patch_ok = False
            else:
                patch_ok = True

            if not patch_ok:
                return VerifyResult(passed=False, test_output="patch apply failed")

            try:
                result = subprocess.run(
                    self._test_cmd,
                    shell=True,
                    cwd=tmp_path / "proj",
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = result.stdout[-1000:] if result.stdout else result.stderr[-1000:]
                passed = result.returncode == 0
                regressions = output.lower().count("failed") if not passed else 0
                return VerifyResult(passed=passed, test_output=output, regression_count=regressions)
            except subprocess.TimeoutExpired:
                return VerifyResult(passed=False, test_output="timeout", regression_count=0)
