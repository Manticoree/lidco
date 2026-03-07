"""Tests for fix_memory — cross-session bug-fix learning."""

from __future__ import annotations

import pytest

from lidco.core.fix_memory import FixMemory, FixPattern, confidence_label
from lidco.core.memory import MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    """Real MemoryStore backed by a temporary directory."""
    return MemoryStore(global_dir=tmp_path / "memory", max_entries=200)


@pytest.fixture()
def fix_memory(store):
    return FixMemory(memory_store=store)


def _record(
    fix_memory: FixMemory,
    *,
    error_type: str = "AttributeError",
    file_module: str = "lidco.core.session",
    function_hint: str = "load_config",
    error_signature: str = "object has no attribute config",
    fix_description: str = "Added None guard before attribute access.",
    diff_summary: str = "+2/-0 lines, added guard",
    confidence: float = 0.85,
    session_id: str = "sess-001",
) -> FixPattern:
    return fix_memory.record(
        error_type=error_type,
        file_module=file_module,
        function_hint=function_hint,
        error_signature=error_signature,
        fix_description=fix_description,
        diff_summary=diff_summary,
        confidence=confidence,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Test 1: record() returns FixPattern with correct fields
# ---------------------------------------------------------------------------


class TestRecord:
    def test_record_returns_fix_pattern_with_fields(self, fix_memory):
        pattern = _record(fix_memory)

        assert isinstance(pattern, FixPattern)
        assert pattern.error_type == "AttributeError"
        assert pattern.file_module == "lidco.core.session"
        assert pattern.function_hint == "load_config"
        assert pattern.error_signature == "object has no attribute config"
        assert pattern.fix_description == "Added None guard before attribute access."
        assert pattern.diff_summary == "+2/-0 lines, added guard"
        assert pattern.confidence == 0.85
        assert pattern.session_id == "sess-001"
        assert pattern.created_at != ""


# ---------------------------------------------------------------------------
# Test 2: find_similar() with exact error_type+file_module match
# ---------------------------------------------------------------------------


class TestFindSimilarExactMatch:
    def test_exact_match_found(self, fix_memory):
        _record(fix_memory)
        results = fix_memory.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="irrelevant message",
        )
        assert len(results) >= 1
        assert results[0].error_type == "AttributeError"
        assert results[0].file_module == "lidco.core.session"


# ---------------------------------------------------------------------------
# Test 3: find_similar() with keyword match in error_message
# ---------------------------------------------------------------------------


class TestFindSimilarKeywordMatch:
    def test_keyword_match_found(self, fix_memory):
        _record(
            fix_memory,
            error_type="TypeError",
            file_module="lidco.core.other",
            error_signature="integer cannot be divided by string operand",
            confidence=0.6,
        )
        # Use a different error_type/file_module to ensure keyword path fires
        results = fix_memory.find_similar(
            error_type="SomeOtherError",
            file_module="unrelated.module",
            error_message="cannot divided string integer",
        )
        assert any(p.error_type == "TypeError" for p in results)


# ---------------------------------------------------------------------------
# Test 4: find_similar() returns empty list when no matches
# ---------------------------------------------------------------------------


class TestFindSimilarNoMatches:
    def test_no_matches_returns_empty_list(self, fix_memory):
        results = fix_memory.find_similar(
            error_type="ZeroDivisionError",
            file_module="nonexistent.module",
            error_message="completely unrelated blah",
        )
        assert results == []


# ---------------------------------------------------------------------------
# Test 5: find_similar() caps at 3 results
# ---------------------------------------------------------------------------


class TestFindSimilarCapsAtThree:
    def test_results_capped_at_three(self, fix_memory):
        for i in range(6):
            _record(
                fix_memory,
                error_type="AttributeError",
                file_module="lidco.core.session",
                function_hint=f"func_{i}",
                confidence=0.5 + i * 0.05,
            )
        results = fix_memory.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="no attribute",
        )
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# Test 6: find_similar() sorts by confidence desc
# ---------------------------------------------------------------------------


class TestFindSimilarSortOrder:
    def test_sorted_by_confidence_descending(self, fix_memory):
        _record(fix_memory, function_hint="low", confidence=0.3)
        _record(fix_memory, function_hint="high", confidence=0.9)
        _record(fix_memory, function_hint="mid", confidence=0.6)

        results = fix_memory.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="",
        )
        confidences = [p.confidence for p in results]
        assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# Test 7: build_context() returns empty string for no matches
# ---------------------------------------------------------------------------


class TestBuildContextEmpty:
    def test_returns_empty_string_when_no_matches(self, fix_memory):
        ctx = fix_memory.build_context(
            error_type="FooBarError",
            file_module="nowhere",
            error_message="nothing relevant",
        )
        assert ctx == ""


# ---------------------------------------------------------------------------
# Test 8: build_context() returns formatted Markdown with ## header
# ---------------------------------------------------------------------------


class TestBuildContextFormatted:
    def test_returns_markdown_with_header(self, fix_memory):
        _record(fix_memory)
        ctx = fix_memory.build_context(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="",
        )
        assert ctx.startswith("## Past Fixes for Similar Errors")
        assert "AttributeError" in ctx


# ---------------------------------------------------------------------------
# Test 9: confidence_label HIGH for 0.8
# ---------------------------------------------------------------------------


class TestConfidenceLabelHigh:
    def test_high_for_0_8(self):
        assert confidence_label(0.8) == "HIGH"

    def test_high_at_threshold_0_7(self):
        assert confidence_label(0.7) == "HIGH"


# ---------------------------------------------------------------------------
# Test 10: confidence_label MEDIUM for 0.5
# ---------------------------------------------------------------------------


class TestConfidenceLabelMedium:
    def test_medium_for_0_5(self):
        assert confidence_label(0.5) == "MEDIUM"

    def test_medium_at_threshold_0_4(self):
        assert confidence_label(0.4) == "MEDIUM"


# ---------------------------------------------------------------------------
# Test 11: confidence_label LOW for 0.2
# ---------------------------------------------------------------------------


class TestConfidenceLabelLow:
    def test_low_for_0_2(self):
        assert confidence_label(0.2) == "LOW"

    def test_low_for_zero(self):
        assert confidence_label(0.0) == "LOW"


# ---------------------------------------------------------------------------
# Test 12: record() persists to memory_store (can be retrieved)
# ---------------------------------------------------------------------------


class TestRecordPersists:
    def test_pattern_persisted_to_store(self, tmp_path):
        mem_dir = tmp_path / "mem"
        store1 = MemoryStore(global_dir=mem_dir, max_entries=100)
        fm1 = FixMemory(memory_store=store1)
        _record(fm1)

        # Create a fresh store loading from same directory
        store2 = MemoryStore(global_dir=mem_dir, max_entries=100)
        fm2 = FixMemory(memory_store=store2)
        results = fm2.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="",
        )
        assert len(results) >= 1
        assert results[0].function_hint == "load_config"


# ---------------------------------------------------------------------------
# Test 13: same error_type different file_module → only exact match found
# ---------------------------------------------------------------------------


class TestSameTypeDifferentModule:
    def test_different_module_not_exact_matched(self, fix_memory):
        _record(
            fix_memory,
            error_type="AttributeError",
            file_module="lidco.core.session",
            function_hint="func_a",
            confidence=0.9,
        )
        _record(
            fix_memory,
            error_type="AttributeError",
            file_module="lidco.core.config",
            function_hint="func_b",
            confidence=0.5,
        )
        results = fix_memory.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="no attribute xyz",
        )
        modules = [p.file_module for p in results]
        # Exact match for session module must be present
        assert "lidco.core.session" in modules
        # config module may or may not appear (keyword path) but session wins
        assert results[0].file_module == "lidco.core.session"


# ---------------------------------------------------------------------------
# Test 14: record multiple patterns, find_similar returns best ones
# ---------------------------------------------------------------------------


class TestMultiplePatternsReturnsBest:
    def test_best_confidence_patterns_returned(self, fix_memory):
        confidences = [0.9, 0.8, 0.7, 0.6, 0.5]
        for i, conf in enumerate(confidences):
            _record(
                fix_memory,
                function_hint=f"func_{i}",
                confidence=conf,
            )
        results = fix_memory.find_similar(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="",
        )
        assert len(results) == 3
        # Top 3 by confidence: 0.9, 0.8, 0.7
        assert results[0].confidence == 0.9
        assert results[1].confidence == 0.8
        assert results[2].confidence == 0.7


# ---------------------------------------------------------------------------
# Test 15: build_context format includes all FixPattern fields
# ---------------------------------------------------------------------------


class TestBuildContextIncludesAllFields:
    def test_context_includes_all_fields(self, fix_memory):
        _record(
            fix_memory,
            error_type="AttributeError",
            file_module="lidco.core.session",
            function_hint="load_config",
            fix_description="Added None guard before attribute access.",
            diff_summary="+2/-0 lines, added guard",
            confidence=0.85,
        )
        ctx = fix_memory.build_context(
            error_type="AttributeError",
            file_module="lidco.core.session",
            error_message="",
        )
        assert "lidco.core.session" in ctx
        assert "load_config" in ctx
        assert "AttributeError" in ctx
        assert "Added None guard before attribute access." in ctx
        assert "+2/-0 lines, added guard" in ctx
        assert "HIGH" in ctx  # confidence 0.85 → HIGH
