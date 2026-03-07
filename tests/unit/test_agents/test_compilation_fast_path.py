"""Tests for Task 110 — Compilation Fast-Path++ (Q23).

Tests the ``_detect_fast_path_error_type`` helper and
``GraphOrchestrator._build_compilation_hint`` method which wire
``syntax_fixer`` and ``module_advisor`` into the debugger injection pipeline.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.agents.graph import GraphOrchestrator, _detect_fast_path_error_type
from lidco.agents.registry import AgentRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orch() -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(
        content="ok",
        model="m",
        tool_calls=[],
        usage={"total_tokens": 5},
        finish_reason="stop",
        cost_usd=0.0,
    ))
    return GraphOrchestrator(llm=llm, agent_registry=AgentRegistry(), agent_timeout=0)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _detect_fast_path_error_type
# ---------------------------------------------------------------------------


class TestDetectFastPathErrorType:
    def test_syntax_error_detected(self):
        ctx = "File foo.py, line 3\nSyntaxError: expected ':'"
        assert _detect_fast_path_error_type(ctx) == "SyntaxError"

    def test_indentation_error_detected(self):
        ctx = "IndentationError: unexpected indent (foo.py, line 7)"
        assert _detect_fast_path_error_type(ctx) == "IndentationError"

    def test_module_not_found_detected(self):
        ctx = "ModuleNotFoundError: No module named 'pydantics'"
        assert _detect_fast_path_error_type(ctx) == "ModuleNotFoundError"

    def test_import_error_detected(self):
        ctx = "ImportError: cannot import name 'Foo' from 'bar'"
        assert _detect_fast_path_error_type(ctx) == "ImportError"

    def test_name_error_detected(self):
        ctx = "NameError: name 'foo' is not defined"
        assert _detect_fast_path_error_type(ctx) == "NameError"

    def test_unknown_context_returns_none(self):
        ctx = "Everything is fine, no errors here"
        assert _detect_fast_path_error_type(ctx) is None

    def test_empty_context_returns_none(self):
        assert _detect_fast_path_error_type("") is None

    def test_priority_syntax_over_import(self):
        # SyntaxError comes before ImportError in _FAST_PATH_PRIORITY — must win
        ctx = "SyntaxError: invalid syntax\nImportError: missing module"
        assert _detect_fast_path_error_type(ctx) == "SyntaxError"

    def test_module_not_found_not_shadowed_by_import_error(self):
        # "ImportError" is a substring of "ModuleNotFoundError" in raw text.
        # Word-boundary matching must detect ModuleNotFoundError correctly.
        ctx = "ModuleNotFoundError: No module named 'pydantic'"
        assert _detect_fast_path_error_type(ctx) == "ModuleNotFoundError"

    def test_tab_error_detected(self):
        ctx = "TabError: inconsistent use of tabs and spaces in indentation"
        assert _detect_fast_path_error_type(ctx) == "TabError"


# ---------------------------------------------------------------------------
# _build_compilation_hint — SyntaxError branch
# ---------------------------------------------------------------------------


class TestBuildCompilationHintSyntax:
    def test_syntax_error_colon_produces_hint(self):
        orch = _make_orch()
        ctx = "SyntaxError: expected ':'\n  if x > 0"
        hint = _run(orch._build_compilation_hint(ctx, "SyntaxError"))
        assert isinstance(hint, str)
        assert len(hint) > 0
        assert "missing-colon" in hint or "colon" in hint.lower() or "Compilation" in hint

    def test_syntax_error_print_produces_hint(self):
        orch = _make_orch()
        ctx = "SyntaxError: Missing parentheses in call to 'print'\n  print 'hello'"
        hint = _run(orch._build_compilation_hint(ctx, "SyntaxError"))
        assert "print" in hint.lower() or "missing-print" in hint

    def test_indentation_error_produces_hint(self):
        orch = _make_orch()
        ctx = "IndentationError: unexpected indent (foo.py, line 5)"
        hint = _run(orch._build_compilation_hint(ctx, "IndentationError"))
        assert len(hint) > 0
        assert "indent" in hint.lower() or "Compilation" in hint

    def test_tab_error_produces_hint(self):
        orch = _make_orch()
        ctx = "TabError: inconsistent use of tabs and spaces in indentation (foo.py, line 8)"
        hint = _run(orch._build_compilation_hint(ctx, "TabError"))
        assert len(hint) > 0
        assert "tab" in hint.lower() or "indent" in hint.lower() or "Compilation" in hint

    def test_unrecognised_syntax_error_returns_header_only_or_empty(self):
        orch = _make_orch()
        ctx = "SyntaxError: completely unknown weird error message xyz"
        hint = _run(orch._build_compilation_hint(ctx, "SyntaxError"))
        # Must not crash; may be empty or contain a header
        assert isinstance(hint, str)

    def test_hint_contains_section_header(self):
        orch = _make_orch()
        ctx = "SyntaxError: expected ':'"
        hint = _run(orch._build_compilation_hint(ctx, "SyntaxError"))
        # Should have a clear Markdown section heading
        assert hint.startswith("##") or hint == ""


# ---------------------------------------------------------------------------
# _build_compilation_hint — ModuleNotFoundError branch
# ---------------------------------------------------------------------------


class TestBuildCompilationHintModule:
    def test_module_not_found_pil(self):
        orch = _make_orch()
        ctx = "ModuleNotFoundError: No module named 'PIL'"
        hint = _run(orch._build_compilation_hint(ctx, "ModuleNotFoundError"))
        assert len(hint) > 0
        assert "pillow" in hint.lower() or "PIL" in hint

    def test_module_not_found_typo(self):
        orch = _make_orch()
        ctx = "ModuleNotFoundError: No module named 'pydantics'"
        hint = _run(orch._build_compilation_hint(ctx, "ModuleNotFoundError"))
        assert len(hint) > 0
        assert "pydantics" in hint or "module" in hint.lower()

    def test_import_error_with_module_name(self):
        orch = _make_orch()
        ctx = "ModuleNotFoundError: No module named 'cv2'"
        hint = _run(orch._build_compilation_hint(ctx, "ModuleNotFoundError"))
        assert "opencv" in hint.lower() or "cv2" in hint

    def test_import_error_no_module_name_returns_empty_or_safe(self):
        orch = _make_orch()
        ctx = "ImportError: cannot import name 'Foo' from 'bar'"
        hint = _run(orch._build_compilation_hint(ctx, "ImportError"))
        # Should not crash even if no "No module named" pattern found
        assert isinstance(hint, str)

    def test_module_not_found_submodule(self):
        orch = _make_orch()
        ctx = "ModuleNotFoundError: No module named 'numpy.linalg'"
        hint = _run(orch._build_compilation_hint(ctx, "ModuleNotFoundError"))
        assert len(hint) > 0
        assert "numpy" in hint


# ---------------------------------------------------------------------------
# _build_compilation_hint — unknown / NameError branch
# ---------------------------------------------------------------------------


class TestBuildCompilationHintFallback:
    def test_name_error_returns_empty(self):
        orch = _make_orch()
        ctx = "NameError: name 'foo' is not defined"
        hint = _run(orch._build_compilation_hint(ctx, "NameError"))
        # NameError has no specific advisor — should return empty or generic
        assert isinstance(hint, str)

    def test_empty_context_returns_empty(self):
        orch = _make_orch()
        hint = _run(orch._build_compilation_hint("", "SyntaxError"))
        assert isinstance(hint, str)

    def test_never_raises(self):
        orch = _make_orch()
        for etype in ("SyntaxError", "IndentationError", "ModuleNotFoundError", "ImportError", "NameError"):
            result = _run(orch._build_compilation_hint("garbage context @@###", etype))
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _try_compilation_fast_path — gating logic
# ---------------------------------------------------------------------------


class TestTryCompilationFastPath:
    def test_disabled_fast_path_returns_false(self):
        orch = _make_orch()
        orch.set_debug_fast_path(False)
        result = _run(orch._try_compilation_fast_path(
            error_context="SyntaxError: expected ':'",
            file_hint="foo.py",
            error_type="SyntaxError",
        ))
        assert result is False

    def test_unknown_error_type_returns_false(self):
        orch = _make_orch()
        result = _run(orch._try_compilation_fast_path(
            error_context="RuntimeError: something bad",
            file_hint="foo.py",
            error_type="RuntimeError",
        ))
        assert result is False

    def test_missing_file_hint_returns_false(self):
        orch = _make_orch()
        result = _run(orch._try_compilation_fast_path(
            error_context="SyntaxError: expected ':'",
            file_hint=None,
            error_type="SyntaxError",
        ))
        assert result is False

    def test_enabled_syntax_error_returns_false(self):
        # Fast-path does not auto-fix (returns False); it enriches context instead
        orch = _make_orch()
        orch.set_debug_fast_path(True)
        result = _run(orch._try_compilation_fast_path(
            error_context="SyntaxError: expected ':'",
            file_hint="foo.py",
            error_type="SyntaxError",
        ))
        assert result is False
