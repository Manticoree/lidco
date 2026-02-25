"""Tests for GHPRTool and its formatting/fetch helpers."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tools.gh_pr import (
    GHPRTool,
    _fetch_pr_diff,
    _fetch_pr_metadata,
    _format_pr_context,
)


# ---------------------------------------------------------------------------
# Sample PR data
# ---------------------------------------------------------------------------

SAMPLE_PR: dict = {
    "number": 42,
    "title": "Add streaming tool results",
    "state": "OPEN",
    "headRefName": "feature/streaming",
    "baseRefName": "main",
    "additions": 150,
    "deletions": 30,
    "body": "This PR adds streaming support to RunTestsTool and ProfilerTool.",
    "files": [
        {"path": "src/lidco/tools/test_runner.py", "additions": 80, "deletions": 10, "status": "modified"},
        {"path": "src/lidco/tools/profiler.py", "additions": 50, "deletions": 15, "status": "modified"},
        {"path": "tests/unit/test_tools/test_test_runner.py", "additions": 20, "deletions": 5, "status": "modified"},
    ],
    "comments": [
        {
            "body": "Looks good! Great use of asyncio.",
            "author": {"login": "reviewer1"},
            "createdAt": "2025-01-20T10:00:00Z",
        },
        {
            "body": "LGTM, minor nit on the fallback path.",
            "author": {"login": "reviewer2"},
            "createdAt": "2025-01-20T11:00:00Z",
        },
    ],
}

SAMPLE_DIFF = "@@ -1,5 +1,8 @@\n-old line\n+new line\n+another new line"


def _make_process(stdout: bytes, returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestGHPRToolMetadata:
    def test_name(self) -> None:
        assert GHPRTool().name == "gh_pr"

    def test_has_two_parameters(self) -> None:
        params = GHPRTool().parameters
        names = {p.name for p in params}
        assert names == {"number", "include_diff"}

    def test_number_is_required(self) -> None:
        param = next(p for p in GHPRTool().parameters if p.name == "number")
        assert param.required is True

    def test_include_diff_is_optional(self) -> None:
        param = next(p for p in GHPRTool().parameters if p.name == "include_diff")
        assert param.required is False
        assert param.default is True


# ---------------------------------------------------------------------------
# _format_pr_context
# ---------------------------------------------------------------------------

class TestFormatPrContext:
    def test_contains_pr_number_and_title(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "## PR #42" in result
        assert "Add streaming tool results" in result

    def test_contains_branch_and_state(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "feature/streaming" in result
        assert "main" in result
        assert "OPEN" in result

    def test_contains_additions_and_deletions(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "+150" in result
        assert "−30" in result

    def test_contains_changed_files(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "test_runner.py" in result
        assert "profiler.py" in result

    def test_contains_description(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "streaming support" in result

    def test_contains_comments(self) -> None:
        result = _format_pr_context(SAMPLE_PR)
        assert "reviewer1" in result
        assert "Looks good" in result

    def test_empty_body_no_description_header(self) -> None:
        pr = {**SAMPLE_PR, "body": ""}
        result = _format_pr_context(pr)
        assert "### Description" not in result

    def test_empty_files_no_changed_files_header(self) -> None:
        pr = {**SAMPLE_PR, "files": []}
        result = _format_pr_context(pr)
        assert "### Changed Files" not in result

    def test_no_comments_no_comments_header(self) -> None:
        pr = {**SAMPLE_PR, "comments": []}
        result = _format_pr_context(pr)
        assert "### Comments" not in result

    def test_long_body_truncated(self) -> None:
        pr = {**SAMPLE_PR, "body": "x" * 3000}
        result = _format_pr_context(pr)
        assert "truncated" in result


# ---------------------------------------------------------------------------
# _fetch_pr_metadata
# ---------------------------------------------------------------------------

class TestFetchPrMetadata:
    @pytest.mark.asyncio
    async def test_success_returns_parsed_dict(self) -> None:
        proc = _make_process(json.dumps(SAMPLE_PR).encode())
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data, err = await _fetch_pr_metadata("42")
        assert err is None
        assert data is not None
        assert data["number"] == 42

    @pytest.mark.asyncio
    async def test_gh_not_installed(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            data, err = await _fetch_pr_metadata("42")
        assert data is None
        assert "gh CLI not installed" in (err or "")

    @pytest.mark.asyncio
    async def test_nonzero_returncode_returns_stderr(self) -> None:
        proc = _make_process(b"", returncode=1, stderr=b"could not find PR")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data, err = await _fetch_pr_metadata("999")
        assert data is None
        assert "could not find PR" in (err or "")

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self) -> None:
        proc = _make_process(b"not valid json {{")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            data, err = await _fetch_pr_metadata("42")
        assert data is None
        assert err is not None

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=asyncio.TimeoutError,
        ):
            data, err = await _fetch_pr_metadata("42")
        assert data is None
        assert "timed out" in (err or "").lower()


# ---------------------------------------------------------------------------
# _fetch_pr_diff
# ---------------------------------------------------------------------------

class TestFetchPrDiff:
    @pytest.mark.asyncio
    async def test_returns_diff_text(self) -> None:
        proc = _make_process(SAMPLE_DIFF.encode())
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await _fetch_pr_diff("42")
        assert "@@ -1,5" in result

    @pytest.mark.asyncio
    async def test_nonzero_returncode_returns_empty(self) -> None:
        proc = _make_process(b"", returncode=1)
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await _fetch_pr_diff("42")
        assert result == ""

    @pytest.mark.asyncio
    async def test_file_not_found_returns_empty(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await _fetch_pr_diff("42")
        assert result == ""


# ---------------------------------------------------------------------------
# GHPRTool._run()
# ---------------------------------------------------------------------------

class TestGHPRToolRun:
    def setup_method(self) -> None:
        self.tool = GHPRTool()

    @pytest.mark.asyncio
    async def test_no_number_returns_error(self) -> None:
        result = await self.tool._run(number="")
        assert result.success is False
        assert "required" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_gh_failure_propagates_error(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await self.tool._run(number="42")
        assert result.success is False
        assert "gh CLI not installed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_success_returns_formatted_output(self) -> None:
        meta_proc = _make_process(json.dumps(SAMPLE_PR).encode())
        diff_proc = _make_process(SAMPLE_DIFF.encode())

        call_count = 0

        async def _fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # first call = gh pr view, second = gh pr diff
            return meta_proc if call_count == 1 else diff_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
            result = await self.tool._run(number="42")

        assert result.success is True
        assert "## PR #42" in result.output
        assert "Add streaming tool results" in result.output

    @pytest.mark.asyncio
    async def test_include_diff_false_skips_diff(self) -> None:
        meta_proc = _make_process(json.dumps(SAMPLE_PR).encode())

        with patch("asyncio.create_subprocess_exec", return_value=meta_proc) as mock_exec:
            result = await self.tool._run(number="42", include_diff=False)

        # gh pr diff should NOT have been called — only one subprocess call
        assert mock_exec.call_count == 1
        assert "Unified Diff" not in result.output
        assert result.success is True

    @pytest.mark.asyncio
    async def test_include_diff_appends_diff_section(self) -> None:
        meta_proc = _make_process(json.dumps(SAMPLE_PR).encode())
        diff_proc = _make_process(SAMPLE_DIFF.encode())
        call_count = 0

        async def _fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return meta_proc if call_count == 1 else diff_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
            result = await self.tool._run(number="42", include_diff=True)

        assert "Unified Diff" in result.output
        assert "@@ -1,5" in result.output

    @pytest.mark.asyncio
    async def test_metadata_extracted(self) -> None:
        meta_proc = _make_process(json.dumps(SAMPLE_PR).encode())
        diff_proc = _make_process(b"")
        call_count = 0

        async def _fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return meta_proc if call_count == 1 else diff_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
            result = await self.tool._run(number="42")

        assert result.metadata["number"] == 42
        assert result.metadata["title"] == "Add streaming tool results"
        assert result.metadata["state"] == "OPEN"
        assert result.metadata["files_count"] == 3
        assert result.metadata["additions"] == 150
        assert result.metadata["deletions"] == 30

    @pytest.mark.asyncio
    async def test_long_diff_truncated(self) -> None:
        meta_proc = _make_process(json.dumps(SAMPLE_PR).encode())
        long_diff = "+" + "x" * 10000
        diff_proc = _make_process(long_diff.encode())
        call_count = 0

        async def _fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return meta_proc if call_count == 1 else diff_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
            result = await self.tool._run(number="42", include_diff=True)

        assert "truncated" in result.output
