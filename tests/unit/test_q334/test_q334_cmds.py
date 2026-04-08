"""Tests for lidco.cli.commands.q334_cmds — CLI commands."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name, description, handler):
        self.commands[name] = (description, handler)


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q334_cmds import register_q334_commands
    reg = _FakeRegistry()
    register_q334_commands(reg)
    return reg


class TestQ334CommandsRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        reg = _build_registry()
        expected = {"analyze-writing", "improve-writing", "writing-template", "glossary"}
        self.assertEqual(set(reg.commands.keys()), expected)


class TestAnalyzeWritingCommand(unittest.TestCase):
    def setUp(self):
        reg = _build_registry()
        _, self.handler = reg.commands["analyze-writing"]

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_full_analysis(self):
        result = _run(self.handler("The cat sat on the mat. Dogs are great."))
        self.assertIn("Words:", result)
        self.assertIn("Readability:", result)

    def test_readability_subcommand(self):
        result = _run(self.handler("readability The cat sat on the mat."))
        self.assertIn("Readability:", result)
        self.assertIn("Grade level:", result)

    def test_jargon_subcommand(self):
        result = _run(self.handler("jargon We should leverage this."))
        self.assertIn("Jargon detected", result)
        self.assertIn("leverage", result)

    def test_jargon_none(self):
        result = _run(self.handler("jargon The cat sat on the mat."))
        self.assertIn("No jargon", result)

    def test_tone_subcommand(self):
        result = _run(self.handler("tone The system is operational."))
        self.assertIn("Tone:", result)
        self.assertIn("Formality:", result)

    def test_consistency_subcommand(self):
        result = _run(self.handler("consistency Use frontend and front-end together."))
        self.assertIn("Consistency issues", result)

    def test_consistency_none(self):
        result = _run(self.handler("consistency The cat sat on the mat."))
        self.assertIn("No consistency issues", result)

    def test_readability_no_text(self):
        result = _run(self.handler("readability"))
        self.assertIn("Usage", result)

    def test_jargon_no_text(self):
        result = _run(self.handler("jargon"))
        self.assertIn("Usage", result)

    def test_tone_no_text(self):
        result = _run(self.handler("tone"))
        self.assertIn("Usage", result)

    def test_consistency_no_text(self):
        result = _run(self.handler("consistency"))
        self.assertIn("Usage", result)


class TestImproveWritingCommand(unittest.TestCase):
    def setUp(self):
        reg = _build_registry()
        _, self.handler = reg.commands["improve-writing"]

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_full_improve(self):
        result = _run(self.handler("In order to fix this we need help."))
        self.assertIn("Suggestions:", result)

    def test_simplify_subcommand(self):
        result = _run(self.handler("simplify In order to fix this we act."))
        self.assertIn("Simplifications", result)

    def test_simplify_none(self):
        result = _run(self.handler("simplify The cat sat."))
        self.assertIn("No simplification", result)

    def test_grammar_subcommand(self):
        result = _run(self.handler("grammar You could of done better."))
        self.assertIn("Grammar issues", result)

    def test_grammar_none(self):
        result = _run(self.handler("grammar The system is working."))
        self.assertIn("No grammar issues", result)

    def test_structure_subcommand(self):
        result = _run(self.handler("structure Short sentences are fine."))
        self.assertIn("Structure looks good", result)

    def test_examples_subcommand(self):
        result = _run(self.handler("examples The API endpoint accepts parameters and returns JSON data with nested objects and arrays and more stuff back to the caller."))
        self.assertIn("Example suggestions", result)

    def test_examples_none(self):
        result = _run(self.handler("examples Short."))
        self.assertIn("No example", result)

    def test_simplify_no_text(self):
        result = _run(self.handler("simplify"))
        self.assertIn("Usage", result)

    def test_grammar_no_text(self):
        result = _run(self.handler("grammar"))
        self.assertIn("Usage", result)

    def test_structure_no_text(self):
        result = _run(self.handler("structure"))
        self.assertIn("Usage", result)

    def test_examples_no_text(self):
        result = _run(self.handler("examples"))
        self.assertIn("Usage", result)


class TestWritingTemplateCommand(unittest.TestCase):
    def setUp(self):
        reg = _build_registry()
        _, self.handler = reg.commands["writing-template"]

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list(self):
        result = _run(self.handler("list"))
        self.assertIn("Templates", result)
        self.assertIn("RFC", result)

    def test_show(self):
        result = _run(self.handler("show RFC"))
        self.assertIn("Template: RFC", result)
        self.assertIn("Sections:", result)

    def test_show_not_found(self):
        result = _run(self.handler("show nonexistent"))
        self.assertIn("not found", result)

    def test_show_no_name(self):
        result = _run(self.handler("show"))
        self.assertIn("Usage", result)

    def test_render(self):
        result = _run(self.handler("render RFC author=Alice"))
        self.assertIn("# RFC", result)

    def test_render_not_found(self):
        result = _run(self.handler("render nonexistent"))
        self.assertIn("not found", result)

    def test_render_no_name(self):
        result = _run(self.handler("render"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


class TestGlossaryCommand(unittest.TestCase):
    def setUp(self):
        reg = _build_registry()
        _, self.handler = reg.commands["glossary"]

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("empty", result)

    def test_add(self):
        result = _run(self.handler("add API Application Programming Interface"))
        self.assertIn("Added", result)
        self.assertIn("API", result)

    def test_add_no_args(self):
        result = _run(self.handler("add"))
        self.assertIn("Usage", result)

    def test_remove_not_found(self):
        result = _run(self.handler("remove nonexistent"))
        self.assertIn("not found", result)

    def test_search_no_query(self):
        result = _run(self.handler("search"))
        self.assertIn("Usage", result)

    def test_scan(self):
        result = _run(self.handler("scan The API uses redis for caching."))
        self.assertIn("Defined terms found:", result)
        self.assertIn("Undefined terms:", result)

    def test_scan_no_text(self):
        result = _run(self.handler("scan"))
        self.assertIn("Usage", result)

    def test_export_empty(self):
        result = _run(self.handler("export"))
        self.assertEqual(result, "[]")

    def test_import_valid(self):
        data = '[{"term":"API","definition":"test","aliases":[],"related":[]}]'
        result = _run(self.handler(f"import {data}"))
        self.assertIn("Imported 1", result)

    def test_import_invalid(self):
        result = _run(self.handler("import not-json"))
        self.assertIn("Error", result)

    def test_import_no_data(self):
        result = _run(self.handler("import"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
