"""Tests for Q329 — CLI commands."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestQ329Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q329_cmds import register_q329_commands
        self.registry = _FakeRegistry()
        register_q329_commands(self.registry)

    def _handler(self, name: str):
        return self.registry.commands[name][1]

    # -- Registration --
    def test_all_commands_registered(self) -> None:
        expected = {"knowledge", "knowledge-search", "knowledge-graph", "knowledge-update"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /knowledge --
    def test_knowledge_no_args(self) -> None:
        result = _run(self._handler("knowledge")(""))
        self.assertIn("Usage", result)

    def test_knowledge_types(self) -> None:
        result = _run(self._handler("knowledge")("types"))
        self.assertIn("design_pattern", result)
        self.assertIn("business_rule", result)

    def test_knowledge_extract_no_file(self) -> None:
        result = _run(self._handler("knowledge")("extract"))
        self.assertIn("Usage", result)

    def test_knowledge_extract_file(self) -> None:
        source = 'class TestClass:\n    """A test."""\n    pass\n'
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            path = f.name
        try:
            result = _run(self._handler("knowledge")(f'extract "{path}"'))
            self.assertIn("Extracted", result)
            self.assertIn("TestClass", result)
        finally:
            os.unlink(path)

    def test_knowledge_extract_missing_file(self) -> None:
        result = _run(self._handler("knowledge")("extract /nonexistent.py"))
        self.assertIn("Error", result)

    def test_knowledge_extract_source(self) -> None:
        result = _run(self._handler("knowledge")("extract-source class Foo:\\n    pass"))
        self.assertIn("Extracted", result)

    def test_knowledge_unknown_subcmd(self) -> None:
        result = _run(self._handler("knowledge")("nope"))
        self.assertIn("Unknown", result)

    # -- /knowledge-search --
    def test_knowledge_search_no_args(self) -> None:
        result = _run(self._handler("knowledge-search")(""))
        self.assertIn("Usage", result)

    def test_knowledge_search_query(self) -> None:
        result = _run(self._handler("knowledge-search")("auth"))
        self.assertIn("No results", result)

    def test_knowledge_search_concept_no_name(self) -> None:
        result = _run(self._handler("knowledge-search")("concept"))
        self.assertIn("Usage", result)

    def test_knowledge_search_concept(self) -> None:
        result = _run(self._handler("knowledge-search")("concept singleton"))
        # Empty graph so no results
        self.assertIn("No results", result)

    def test_knowledge_search_answer_no_question(self) -> None:
        result = _run(self._handler("knowledge-search")("answer"))
        self.assertIn("Usage", result)

    def test_knowledge_search_answer(self) -> None:
        result = _run(self._handler("knowledge-search")("answer how does auth work"))
        self.assertIn("don't have information", result)

    # -- /knowledge-graph --
    def test_knowledge_graph_no_args(self) -> None:
        result = _run(self._handler("knowledge-graph")(""))
        self.assertIn("Usage", result)

    def test_knowledge_graph_stats(self) -> None:
        result = _run(self._handler("knowledge-graph")("stats"))
        self.assertIn("Entities: 0", result)

    def test_knowledge_graph_entity_missing(self) -> None:
        result = _run(self._handler("knowledge-graph")("entity foo"))
        self.assertIn("not found", result)

    def test_knowledge_graph_entity_no_id(self) -> None:
        result = _run(self._handler("knowledge-graph")("entity"))
        self.assertIn("Usage", result)

    def test_knowledge_graph_neighbors_no_id(self) -> None:
        result = _run(self._handler("knowledge-graph")("neighbors"))
        self.assertIn("Usage", result)

    def test_knowledge_graph_neighbors(self) -> None:
        result = _run(self._handler("knowledge-graph")("neighbors x"))
        self.assertIn("No neighbors", result)

    def test_knowledge_graph_path_missing_args(self) -> None:
        result = _run(self._handler("knowledge-graph")("path a"))
        self.assertIn("Usage", result)

    def test_knowledge_graph_path(self) -> None:
        result = _run(self._handler("knowledge-graph")("path a b"))
        self.assertIn("No path", result)

    def test_knowledge_graph_types(self) -> None:
        result = _run(self._handler("knowledge-graph")("types"))
        self.assertIn("file", result)
        self.assertIn("function", result)

    def test_knowledge_graph_unknown_subcmd(self) -> None:
        result = _run(self._handler("knowledge-graph")("nope"))
        self.assertIn("Unknown", result)

    # -- /knowledge-update --
    def test_knowledge_update_no_args(self) -> None:
        result = _run(self._handler("knowledge-update")(""))
        self.assertIn("Usage", result)

    def test_knowledge_update_status(self) -> None:
        result = _run(self._handler("knowledge-update")("status"))
        self.assertIn("Tracked files: 0", result)

    def test_knowledge_update_dir_no_path(self) -> None:
        result = _run(self._handler("knowledge-update")("dir"))
        self.assertIn("Usage", result)

    def test_knowledge_update_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = os.path.join(tmpdir, "a.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('class A:\n    pass\n')
            result = _run(self._handler("knowledge-update")(f"dir {tmpdir}"))
            self.assertIn("Scanned", result)
            self.assertIn("changed", result)

    def test_knowledge_update_files(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write('x = 1\n')
            f.flush()
            path = f.name
        try:
            result = _run(self._handler("knowledge-update")(path))
            self.assertIn("Updated", result)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
