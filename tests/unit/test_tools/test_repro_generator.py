"""Tests for ReproGeneratorTool."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.repro_generator import ReproGeneratorTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_TEST_CONTENT = """\
from __future__ import annotations
import pytest


def test_something():
    assert 1 + 1 == 3  # intentionally wrong


def test_other():
    assert True
"""

_FAILURE_OUTPUT = """\
FAILED tests/sample_test.py::test_something - AssertionError: assert 2 == 3
1 failed in 0.1s
"""


def _make_mock_process(stdout: str = "", returncode: int = 1) -> MagicMock:
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout.encode(), b""))
    return process


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReproGeneratorTool:
    async def test_basic_repro_written_to_output_path(self, tmp_path: Path) -> None:
        tool = ReproGeneratorTool()
        out = str(tmp_path / "repro.py")
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(_SAMPLE_TEST_CONTENT)

        with (
            patch(
                "asyncio.create_subprocess_exec",
                return_value=_make_mock_process(_FAILURE_OUTPUT, returncode=1),
            ),
        ):
            result = await tool.execute(
                failing_test=f"{test_file}::test_something",
                output_path=out,
            )

        assert Path(out).exists()
        assert result.success is True

    async def test_output_mentions_minimal_repro_written_to(self, tmp_path: Path) -> None:
        tool = ReproGeneratorTool()
        out = str(tmp_path / "repro.py")
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(_SAMPLE_TEST_CONTENT)

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(_FAILURE_OUTPUT, returncode=1),
        ):
            result = await tool.execute(
                failing_test=f"{test_file}::test_something",
                output_path=out,
            )

        assert "Minimal repro written to" in result.output

    async def test_test_path_parsed_from_double_colon(self, tmp_path: Path) -> None:
        """File path is correctly extracted from 'file.py::test_name' format."""
        tool = ReproGeneratorTool()
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(_SAMPLE_TEST_CONTENT)
        out = str(tmp_path / "repro.py")

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(_FAILURE_OUTPUT, returncode=1),
        ):
            result = await tool.execute(
                failing_test=f"{test_file}::test_something",
                output_path=out,
            )

        # Only the test function should appear (not test_other)
        repro_content = Path(out).read_text()
        assert "test_something" in repro_content

    async def test_set_llm_method_exists_and_stores_llm(self) -> None:
        tool = ReproGeneratorTool()
        fake_llm = MagicMock()
        tool.set_llm(fake_llm)
        assert tool._llm is fake_llm

    async def test_output_path_default_is_lidco_minimal_repro(self) -> None:
        tool = ReproGeneratorTool()
        param_map = {p.name: p for p in tool.parameters}
        assert param_map["output_path"].default == ".lidco/minimal_repro.py"

    async def test_repro_verification_runs_generated_file(self, tmp_path: Path) -> None:
        tool = ReproGeneratorTool()
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(_SAMPLE_TEST_CONTENT)
        out = str(tmp_path / "repro.py")

        call_args_list: list[tuple[object, ...]] = []

        async def mock_subprocess(*args: object, **kwargs: object) -> MagicMock:
            call_args_list.append(args)
            return _make_mock_process(_FAILURE_OUTPUT, returncode=1)

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await tool.execute(
                failing_test=f"{test_file}::test_something",
                output_path=out,
            )

        # At least 2 subprocess calls: one to capture failure, one to verify repro
        assert len(call_args_list) >= 2
        # The last call should reference the output path
        last_args = call_args_list[-1]
        assert out in last_args

    async def test_metadata_has_output_path_field(self, tmp_path: Path) -> None:
        tool = ReproGeneratorTool()
        out = str(tmp_path / "repro.py")
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(_SAMPLE_TEST_CONTENT)

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process(_FAILURE_OUTPUT, returncode=1),
        ):
            result = await tool.execute(
                failing_test=f"{test_file}::test_something",
                output_path=out,
            )

        assert result.metadata.get("output_path") == out

    async def test_nonexistent_test_file_returns_graceful_error(
        self, tmp_path: Path
    ) -> None:
        tool = ReproGeneratorTool()
        out = str(tmp_path / "repro.py")

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_mock_process("", returncode=1),
        ):
            result = await tool.execute(
                failing_test="nonexistent_path/test_missing.py::test_gone",
                output_path=out,
            )

        assert result.success is False
        assert "not found" in result.error or "not found" in result.output or result.error is not None
