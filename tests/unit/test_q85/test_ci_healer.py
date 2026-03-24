"""Tests for CIPipelineHealer (T557)."""
from __future__ import annotations
import asyncio
import sys
import pytest
from lidco.review.ci_healer import CIPipelineHealer, CIFailure, HealResult, _parse_failures


def test_parse_failures_pytest():
    output = "FAILED tests/test_foo.py::test_bar - AssertionError"
    failures = _parse_failures(output)
    assert any(f.step == "pytest" for f in failures)


def test_parse_failures_ruff():
    output = "Found 3 errors. ruff check failed"
    failures = _parse_failures(output)
    assert any(f.step == "ruff" for f in failures)


def test_parse_failures_empty_output():
    failures = _parse_failures("")
    assert failures == []


def test_heal_passing_command():
    healer = CIPipelineHealer(max_attempts=2)
    result = asyncio.run(healer.heal(f"{sys.executable} -c \"print('ok')\""))
    assert result.success is True
    assert result.attempts == 1


def test_heal_failing_no_fixer():
    healer = CIPipelineHealer(max_attempts=2)
    result = asyncio.run(healer.heal(f"{sys.executable} -c \"import sys; sys.exit(1)\""))
    assert result.success is False
    assert result.attempts == 1


def test_heal_with_fixer(tmp_path):
    script = tmp_path / "script.py"
    script.write_text("import sys\nsys.exit(1)\n")
    calls = [0]

    async def fixer(failures):
        calls[0] += 1
        return {str(script): "import sys\nsys.exit(0)\n"}

    healer = CIPipelineHealer(fixer_callback=fixer, max_attempts=3, cwd=str(tmp_path))
    result = asyncio.run(healer.heal(f"{sys.executable} {script}"))
    assert result.success is True
    assert calls[0] == 1


def test_format_report():
    healer = CIPipelineHealer()
    result = asyncio.run(healer.heal(f"{sys.executable} -c \"print('ok')\""))
    report = result.format_report()
    assert "HEALED" in report or "CI Heal" in report


def test_heal_result_history():
    healer = CIPipelineHealer(max_attempts=1)
    result = asyncio.run(healer.heal(f"{sys.executable} -c \"print('ok')\""))
    assert len(result.history) == 1
    assert result.history[0].passed is True
