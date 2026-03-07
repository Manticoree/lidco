"""Tests for _verify_one_assumption() and _verify_assumptions_node()."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.agents.base import AgentResponse, TokenUsage
from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch(project_dir: Path | None = None) -> GraphOrchestrator:
    llm = MagicMock()
    reg = AgentRegistry()
    return GraphOrchestrator(
        llm=llm,
        agent_registry=reg,
        agent_timeout=0,
        project_dir=project_dir,
    )


def _make_plan_response(content: str) -> AgentResponse:
    return AgentResponse(
        content=content,
        tool_calls_made=[],
        iterations=1,
        model_used="test",
        token_usage=TokenUsage(total_tokens=10, total_cost_usd=0.0),
    )


def _base_state(plan_content: str, assumptions: list[str] | None = None) -> dict:
    return {
        "user_message": "do task",
        "context": "",
        "plan_response": _make_plan_response(plan_content),
        "plan_assumptions": assumptions or [],
        "accumulated_tokens": 0,
        "accumulated_cost_usd": 0.0,
    }


# ── TestVerifyOneAssumption ───────────────────────────────────────────────────


class TestVerifyOneAssumption:
    def test_file_exists_verified(self, tmp_path: Path):
        """File in project_dir with known extension → verified."""
        (tmp_path / "myfile.py").write_text("x = 1")
        text = "- `myfile.py` exists [⚠ Unverified]"
        status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "verified"
        assert detail == ""

    def test_file_not_found_wrong(self, tmp_path: Path):
        """File that doesn't exist anywhere in project → wrong."""
        text = "- `totally_missing_abc_xyz.py` must exist [⚠ Unverified]"
        status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "wrong"
        assert "file not found" in detail

    def test_file_found_by_rglob_verified(self, tmp_path: Path):
        """File in subdirectory found via rglob → verified."""
        subdir = tmp_path / "src" / "mypackage"
        subdir.mkdir(parents=True)
        (subdir / "deep_file.py").write_text("")
        # Give relative path that doesn't exist at root but is found by rglob
        text = "- `deep_file.py` should exist [⚠ Unverified]"
        status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "verified"

    def test_module_importable_verified(self, tmp_path: Path):
        """Dotted stdlib module → verified via importlib.find_spec."""
        text = "- `os.path` utilities available [⚠ Unverified]"
        status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "verified"

    def test_module_not_importable_wrong(self, tmp_path: Path):
        """Dotted non-existent module → wrong via importlib."""
        text = "- `nonexistent.xyz.abc.impossible` should be importable [⚠ Unverified]"
        status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "wrong"
        assert "module not importable" in detail

    def test_dotted_module_importable_verified(self, tmp_path: Path):
        """Dotted stdlib module like `os.path` → verified."""
        text = "- `os.path` utilities available [⚠ Unverified]"
        status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "verified"

    def test_version_string_not_treated_as_module(self, tmp_path: Path):
        """Token like `3.11` has non-identifier parts → no module check, skip."""
        text = "- Python `3.11` or newer required [⚠ Unverified]"
        # Should not try to import "3" or "11" — parts are not identifiers
        status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        # Either skip or wrong, but NOT a crash
        assert status in ("skip", "wrong", "verified")

    def test_symbol_found_via_grep_verified(self, tmp_path: Path):
        """Backtick symbol found by grep → verified."""
        text = "- `MySpecialClass` exists in codebase [⚠ Unverified]"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "src/foo.py\n"
        with patch("subprocess.run", return_value=mock_result):
            status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "verified"

    def test_symbol_not_found_via_grep_wrong(self, tmp_path: Path):
        """Backtick symbol not found by grep → wrong."""
        text = "- `MissingSymbolXyzAbc` should be defined [⚠ Unverified]"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "wrong"
        assert "symbol not found" in detail

    def test_grep_exception_skips_symbol(self, tmp_path: Path):
        """Subprocess raises (no grep on PATH) → skip, no penalty."""
        text = "- `SomeFunction` is available [⚠ Unverified]"
        with patch("subprocess.run", side_effect=FileNotFoundError("grep not found")):
            status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        # No grep → can't verify → skip
        assert status == "skip"

    def test_no_backtick_tokens_skip(self, tmp_path: Path):
        """Assumption with no backtick tokens → skip."""
        text = "- Existing tests should still pass [⚠ Unverified]"
        status, _ = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "skip"

    def test_multiple_tokens_wrong_if_any_fail(self, tmp_path: Path):
        """One token passes, another fails → wrong overall."""
        # `os` exists; `totally_missing_file_xyz.py` does not
        text = "- `os` and `totally_missing_file_xyz.py` [⚠ Unverified]"
        status, detail = GraphOrchestrator._verify_one_assumption(text, tmp_path)
        assert status == "wrong"

    def test_never_raises(self, tmp_path: Path):
        """Garbage input never causes an exception."""
        text = "- ```some weird ``nested` backticks [⚠ Unverified]"
        try:
            GraphOrchestrator._verify_one_assumption(text, tmp_path)
        except Exception as e:
            pytest.fail(f"_verify_one_assumption raised: {e}")


# ── TestVerifyAssumptionsNode ─────────────────────────────────────────────────


_PLAN_WITH_UNVERIFIED = """\
**Assumptions:**
- `src/lidco/agents/graph.py` exists [⚠ Unverified]
- All existing tests pass [✓ Verified]

**Steps:**
1. Do the thing
"""

_PLAN_NO_UNVERIFIED = """\
**Assumptions:**
- Everything is fine [✓ Verified]

**Steps:**
1. Go
"""


def _run_node_with_mock(plan_content: str, assumptions: list[str], verify_return: tuple) -> dict:
    """Run _verify_assumptions_node with mocked _verify_one_assumption."""
    orch = _make_orch()
    state = _base_state(plan_content, assumptions)
    with patch.object(GraphOrchestrator, "_verify_one_assumption", return_value=verify_return):
        return asyncio.run(orch._verify_assumptions_node(state))


class TestVerifyAssumptionsNode:
    def test_no_unverified_assumptions_passthrough(self):
        """Plan with no [⚠ Unverified] → state passes through, plan_bad_assumptions=[]."""
        orch = _make_orch()
        state = _base_state(
            _PLAN_NO_UNVERIFIED,
            ["- Everything is fine [✓ Verified]"],
        )
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert result.get("plan_bad_assumptions") == []
        # Plan content unchanged
        assert result["plan_response"].content == _PLAN_NO_UNVERIFIED

    def test_no_plan_response_passthrough(self):
        """No plan_response → returns {plan_bad_assumptions: []}."""
        orch = _make_orch()
        state = {
            "user_message": "task",
            "context": "",
            "plan_response": None,
            "plan_assumptions": ["- something [⚠ Unverified]"],
            "accumulated_tokens": 0,
            "accumulated_cost_usd": 0.0,
        }
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert result.get("plan_bad_assumptions") == []

    def test_verified_marker_replaces_unverified(self):
        """When verification passes → [⚠ Unverified] replaced by [✓ Verified]."""
        assumption = "- `src/lidco/agents/graph.py` exists [⚠ Unverified]"
        result = _run_node_with_mock(_PLAN_WITH_UNVERIFIED, [assumption], ("verified", ""))
        content = result["plan_response"].content
        assert "[✓ Verified]" in content
        assert "[⚠ Unverified]" not in content

    def test_wrong_marker_replaces_unverified(self):
        """When verification fails → [⚠ Unverified] replaced by [✗ Wrong: ...]."""
        assumption = "- `src/lidco/agents/graph.py` exists [⚠ Unverified]"
        result = _run_node_with_mock(
            _PLAN_WITH_UNVERIFIED, [assumption], ("wrong", "file not found: src/lidco/agents/graph.py")
        )
        content = result["plan_response"].content
        assert "[✗ Wrong:" in content
        assert "[⚠ Unverified]" not in content

    def test_bad_assumptions_stored_in_state(self):
        """Failed verification → plan_bad_assumptions is non-empty."""
        assumption = "- `missing.py` required [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("wrong", "file not found: missing.py"))
        assert len(result["plan_bad_assumptions"]) == 1

    def test_verified_assumption_not_in_bad_list(self):
        """Verified assumption → not added to plan_bad_assumptions."""
        assumption = "- `os.path` available [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("verified", ""))
        assert result["plan_bad_assumptions"] == []

    def test_bad_assumptions_section_appended_to_plan(self):
        """Failed assumption → ## Assumption Verification Issues section added."""
        assumption = "- `ghost.py` must exist [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("wrong", "file not found: ghost.py"))
        content = result["plan_response"].content
        assert "## Assumption Verification Issues" in content

    def test_no_verification_section_when_all_verified(self):
        """All assumptions pass → no ## Assumption Verification Issues appended."""
        assumption = "- `os` importable [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("verified", ""))
        content = result["plan_response"].content
        assert "## Assumption Verification Issues" not in content

    def test_skip_status_leaves_plan_unchanged(self):
        """'skip' status → no annotation added, plan unchanged."""
        assumption = "- No breaking changes in API [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("skip", ""))
        content = result["plan_response"].content
        assert "[⚠ Unverified]" in content  # marker untouched
        assert result["plan_bad_assumptions"] == []

    def test_plan_assumptions_updated_after_annotation(self):
        """plan_assumptions list reflects annotated text after verification."""
        assumption = "- `os` available [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        result = _run_node_with_mock(plan, [assumption], ("verified", ""))
        updated = result.get("plan_assumptions", [])
        assert any("[✓ Verified]" in a for a in updated)

    def test_status_callback_fired(self):
        """Status callback is called during verification."""
        orch = _make_orch()
        calls: list[str] = []
        orch.set_status_callback(lambda s: calls.append(s))
        assumption = "- `os` available [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        state = _base_state(plan, [assumption])
        with patch.object(GraphOrchestrator, "_verify_one_assumption", return_value=("verified", "")):
            asyncio.run(orch._verify_assumptions_node(state))
        assert any("проверка" in s.lower() or "допущени" in s.lower() for s in calls)

    def test_real_file_verified_end_to_end(self, tmp_path: Path):
        """Integration: actual file on disk → verified without mocking."""
        (tmp_path / "real_module.py").write_text("def foo(): pass")
        assumption = "- `real_module.py` must exist [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        orch = _make_orch(project_dir=tmp_path)
        state = _base_state(plan, [assumption])
        result = asyncio.run(orch._verify_assumptions_node(state))
        content = result["plan_response"].content
        assert "[✓ Verified]" in content
        assert result["plan_bad_assumptions"] == []

    def test_real_missing_file_wrong_end_to_end(self, tmp_path: Path):
        """Integration: file not found → wrong, section appended."""
        assumption = "- `does_not_exist_at_all.py` required [⚠ Unverified]"
        plan = f"**Assumptions:**\n{assumption}\n\n**Steps:**\n1. go\n"
        orch = _make_orch(project_dir=tmp_path)
        state = _base_state(plan, [assumption])
        result = asyncio.run(orch._verify_assumptions_node(state))
        assert len(result["plan_bad_assumptions"]) == 1
        assert "## Assumption Verification Issues" in result["plan_response"].content
