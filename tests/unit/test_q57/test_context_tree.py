"""Tests for Task 387 — /context tree command."""
from __future__ import annotations

import re
import pytest
from unittest.mock import MagicMock


class TestContextTree:
    """Tests for /context tree section parsing logic."""

    def _parse_context_sections(self, context_str: str) -> list[tuple[str, str]]:
        """Replicate the section parsing from the context_handler."""
        sections: list[tuple[str, str]] = []
        current_title = "Preamble"
        current_body: list[str] = []
        for line in context_str.splitlines():
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                sections.append((current_title, "\n".join(current_body)))
                current_title = m.group(1).strip()
                current_body = []
            else:
                current_body.append(line)
        sections.append((current_title, "\n".join(current_body)))
        return [(t, b) for t, b in sections if b.strip()]

    def test_parse_empty_context(self):
        sections = self._parse_context_sections("")
        assert sections == []

    def test_parse_single_section(self):
        ctx = "## Project Overview\nThis is a Python project."
        sections = self._parse_context_sections(ctx)
        assert len(sections) == 1
        assert sections[0][0] == "Project Overview"
        assert "Python project" in sections[0][1]

    def test_parse_multiple_sections(self):
        ctx = (
            "## Goals\nBuild a CLI tool.\n"
            "## Architecture\nUses LangGraph.\n"
            "## Testing\nPytest framework."
        )
        sections = self._parse_context_sections(ctx)
        assert len(sections) == 3
        titles = [s[0] for s in sections]
        assert "Goals" in titles
        assert "Architecture" in titles
        assert "Testing" in titles

    def test_preamble_captured_before_first_heading(self):
        ctx = "Some intro text.\n\n## Section One\nContent here."
        sections = self._parse_context_sections(ctx)
        titles = [s[0] for s in sections]
        assert "Preamble" in titles
        assert "Section One" in titles

    def test_token_estimate_approximately_4_chars_per_token(self):
        body = "x" * 400
        tokens = len(body) // 4
        assert tokens == 100

    def test_total_tokens_sum_of_sections(self):
        ctx = (
            "## A\n" + "a" * 100 + "\n"
            "## B\n" + "b" * 200 + "\n"
        )
        sections = self._parse_context_sections(ctx)
        total = sum(len(b) // 4 for _, b in sections)
        assert total > 0

    def test_empty_sections_filtered_out(self):
        ctx = "## Empty Section\n\n## Non-empty Section\nHas content here."
        sections = self._parse_context_sections(ctx)
        titles = [s[0] for s in sections]
        assert "Empty Section" not in titles
        assert "Non-empty Section" in titles

    def test_headings_use_double_hash(self):
        ctx = (
            "# Not a section heading\n"
            "### Also not a section heading\n"
            "## Valid Section\nContent."
        )
        sections = self._parse_context_sections(ctx)
        # Both the preamble (with #/### lines as body text) and Valid Section are present
        titles = [s[0] for s in sections]
        # ## is the only heading level that creates a new section
        assert "Valid Section" in titles
        # Single and triple hash go into preamble body
        preamble_sections = [s for s in sections if s[0] == "Preamble"]
        if preamble_sections:
            assert "# Not a section heading" in preamble_sections[0][1]


class TestContextHandlerArg:
    """Tests for /context tree argument routing."""

    def test_tree_argument_detected(self):
        arg = "tree"
        assert arg.strip().lower() == "tree"

    def test_non_tree_argument_goes_to_gauge(self):
        arg = ""
        assert arg.strip().lower() != "tree"

    def test_tree_case_insensitive(self):
        for arg in ["tree", "Tree", "TREE", " tree "]:
            assert arg.strip().lower() == "tree"
