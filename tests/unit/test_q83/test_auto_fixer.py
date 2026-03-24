"""Tests for AutoFixer (T544)."""
from __future__ import annotations
import asyncio
import sys
import pytest
from lidco.agents.auto_fixer import AutoFixer, FixIteration, AutoFixResult


def test_run_sync_passing():
    fixer = AutoFixer()
    result = fixer.run_sync(f"{sys.executable} -c \"print('ok')\"")
    assert result.fixed is True
    assert result.returncode == 0


def test_run_sync_failing():
    fixer = AutoFixer()
    result = fixer.run_sync(f"{sys.executable} -c \"import sys; sys.exit(1)\"")
    assert result.fixed is False
    assert result.returncode == 1


def test_run_passes_immediately():
    fixer = AutoFixer(max_iterations=3)
    result = asyncio.run(fixer.run(f"{sys.executable} -c \"print('ok')\""))
    assert result.success is True
    assert result.iterations == 1


def test_run_fails_no_fixer():
    fixer = AutoFixer(max_iterations=2)
    result = asyncio.run(fixer.run(f"{sys.executable} -c \"import sys; sys.exit(1)\""))
    assert result.success is False
    assert result.iterations == 1  # stops after first failure with no fixer


def test_run_with_fixer_callback(tmp_path):
    p = tmp_path / "script.py"
    p.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    call_count = [0]

    async def fixer(output, files):
        call_count[0] += 1
        return {str(p): "import sys\nsys.exit(0)\n"}

    af = AutoFixer(fixer_callback=fixer, max_iterations=3, cwd=str(tmp_path))
    result = asyncio.run(af.run(f"{sys.executable} {p}"))
    assert result.success is True
    assert call_count[0] == 1


def test_run_result_has_history():
    fixer = AutoFixer(max_iterations=2)
    result = asyncio.run(fixer.run(f"{sys.executable} -c \"print('ok')\""))
    assert len(result.history) >= 1
    assert result.history[0].fixed is True


def test_fix_iteration_dataclass():
    fi = FixIteration(iteration=1, command="cmd", returncode=0, stdout="out", stderr="", fixed=True)
    assert fi.fixed is True


def test_auto_fix_result_success_property():
    r = AutoFixResult(success=True, iterations=1)
    assert r.success is True
