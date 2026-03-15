"""Tests for Q42 — SpecWriter (Task 287)."""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.tdd.spec_writer import Spec, SpecWriter


_SAMPLE_SPEC = textwrap.dedent("""\
    ## Goal
    Add binary search to utils.

    ## Background
    We need fast lookups.

    ## Inputs
    - sorted list
    - target value

    ## Outputs
    - index or -1

    ## Acceptance Criteria
    1. Returns correct index for existing element
    2. Returns -1 for missing element
    3. Works on empty list

    ## Edge Cases
    1. Empty list returns -1
    2. Single-element list

    ## Implementation Notes
    Use iterative approach.

    ## Test File Location
    tests/unit/test_binary_search.py

    ## Implementation File Location
    src/mypackage/binary_search.py
""")


@pytest.fixture()
def mock_session():
    session = MagicMock()
    resp = MagicMock()
    resp.content = _SAMPLE_SPEC
    session.orchestrator.handle = AsyncMock(return_value=resp)
    return session


class TestSpec:
    def test_goal_extraction(self):
        spec = Spec(task="test", content=_SAMPLE_SPEC)
        assert "binary search" in spec.goal.lower()

    def test_test_file_extraction(self):
        spec = Spec(task="test", content=_SAMPLE_SPEC)
        assert spec.test_file == "tests/unit/test_binary_search.py"

    def test_impl_file_extraction(self):
        spec = Spec(task="test", content=_SAMPLE_SPEC)
        assert spec.impl_file == "src/mypackage/binary_search.py"

    def test_acceptance_criteria(self):
        spec = Spec(task="test", content=_SAMPLE_SPEC)
        criteria = spec.acceptance_criteria
        assert len(criteria) >= 3
        assert any("correct index" in c.lower() for c in criteria)

    def test_missing_sections_return_defaults(self):
        spec = Spec(task="my task", content="no sections here")
        assert spec.goal == "my task"  # fallback to task
        assert spec.test_file is None
        assert spec.impl_file is None
        assert spec.acceptance_criteria == []


class TestSpecWriter:
    def test_generate_returns_spec(self, mock_session, tmp_path):
        import asyncio
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        spec = asyncio.run(writer.generate("add binary search"))
        assert isinstance(spec, Spec)
        assert "binary search" in spec.content.lower() or spec.task

    def test_save_creates_file(self, mock_session, tmp_path):
        import asyncio
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        spec = Spec(task="my feature", content=_SAMPLE_SPEC)
        path = writer.save(spec)
        assert Path(path).exists()

    def test_save_sets_path_on_spec(self, mock_session, tmp_path):
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        spec = Spec(task="x", content="content")
        writer.save(spec)
        assert spec.path != ""

    def test_list_empty(self, mock_session, tmp_path):
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        assert writer.list_specs() == []

    def test_list_after_save(self, mock_session, tmp_path):
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        spec = Spec(task="feature-a", content=_SAMPLE_SPEC)
        writer.save(spec, filename="feature_a.md")
        specs = writer.list_specs()
        assert len(specs) == 1
        assert specs[0]["name"] == "feature_a"

    def test_load_by_name(self, mock_session, tmp_path):
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        spec = Spec(task="loadable", content=_SAMPLE_SPEC)
        writer.save(spec, filename="loadable.md")
        loaded = writer.load("loadable")
        assert loaded is not None
        assert "binary search" in loaded.content.lower()

    def test_load_nonexistent_returns_none(self, mock_session, tmp_path):
        writer = SpecWriter(mock_session, specs_dir=tmp_path / "specs")
        assert writer.load("ghost") is None

    def test_generate_llm_failure_fallback(self, tmp_path):
        import asyncio
        session = MagicMock()
        session.orchestrator.handle = AsyncMock(side_effect=RuntimeError("LLM down"))
        writer = SpecWriter(session, specs_dir=tmp_path / "specs")
        spec = asyncio.run(writer.generate("fallback task"))
        assert spec is not None
        assert "fallback task" in spec.content
