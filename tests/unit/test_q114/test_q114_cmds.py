"""Tests for Q114 CLI commands (Task 706)."""
import asyncio
import json
import unittest

from lidco.cli.commands.q114_cmds import register, _state


def _make_registry():
    """Create a mock registry that captures registered commands."""
    commands = {}

    class MockRegistry:
        def register(self, cmd):
            commands[cmd.name] = cmd

    reg = MockRegistry()
    register(reg)
    return commands


def _nb_json(cells=None):
    """Build minimal notebook JSON string."""
    if cells is None:
        cells = [{"cell_type": "code", "source": "x = 1", "metadata": {}}]
    return json.dumps({"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": cells})


class TestRegistration(unittest.TestCase):
    def test_notebook_registered(self):
        cmds = _make_registry()
        self.assertIn("notebook", cmds)

    def test_search_registered(self):
        cmds = _make_registry()
        self.assertIn("search", cmds)

    def test_notebook_description(self):
        cmds = _make_registry()
        self.assertIn("notebook", cmds["notebook"].description.lower())

    def test_search_description(self):
        cmds = _make_registry()
        self.assertIn("search", cmds["search"].description.lower())


class TestNotebookOpen(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler

    def test_open_success(self):
        _state["read_fn"] = lambda p: _nb_json()
        result = asyncio.run(self.handler("open test.ipynb"))
        self.assertIn("Opened", result)
        self.assertIn("1 cell", result)

    def test_open_no_path(self):
        result = asyncio.run(self.handler("open"))
        self.assertIn("Usage", result)

    def test_open_invalid_json(self):
        _state["read_fn"] = lambda p: "not json"
        result = asyncio.run(self.handler("open bad.ipynb"))
        self.assertIn("Error", result)

    def test_open_stores_doc_in_state(self):
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))
        self.assertIn("notebook_doc", _state)


class TestNotebookAdd(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler

    def test_add_no_notebook(self):
        result = asyncio.run(self.handler("add code print(1)"))
        self.assertIn("No notebook open", result)

    def test_add_code_cell(self):
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))
        result = asyncio.run(self.handler("add code print(1)"))
        self.assertIn("Added code cell", result)
        self.assertIn("2 cell", result)

    def test_add_markdown_cell(self):
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))
        result = asyncio.run(self.handler("add markdown # Title"))
        self.assertIn("Added markdown cell", result)

    def test_add_missing_args(self):
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))
        result = asyncio.run(self.handler("add"))
        self.assertIn("Usage", result)


class TestNotebookReplace(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))

    def test_replace_success(self):
        result = asyncio.run(self.handler("replace 0 y = 2"))
        self.assertIn("Replaced cell 0", result)

    def test_replace_out_of_bounds(self):
        result = asyncio.run(self.handler("replace 99 x"))
        self.assertIn("Error", result)

    def test_replace_bad_index(self):
        result = asyncio.run(self.handler("replace abc x"))
        self.assertIn("integer", result.lower())

    def test_replace_no_notebook(self):
        _state.clear()
        result = asyncio.run(self.handler("replace 0 x"))
        self.assertIn("No notebook open", result)


class TestNotebookDelete(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))

    def test_delete_success(self):
        result = asyncio.run(self.handler("delete 0"))
        self.assertIn("Deleted cell 0", result)
        self.assertIn("0 cell", result)

    def test_delete_out_of_bounds(self):
        result = asyncio.run(self.handler("delete 99"))
        self.assertIn("Error", result)

    def test_delete_no_notebook(self):
        _state.clear()
        result = asyncio.run(self.handler("delete 0"))
        self.assertIn("No notebook open", result)


class TestNotebookShow(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))

    def test_show_output(self):
        result = asyncio.run(self.handler("show"))
        self.assertIn("Cells: 1", result)
        self.assertIn("code=1", result)

    def test_show_no_notebook(self):
        _state.clear()
        result = asyncio.run(self.handler("show"))
        self.assertIn("No notebook open", result)


class TestNotebookAsk(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["notebook"].handler
        _state["read_fn"] = lambda p: _nb_json()
        asyncio.run(self.handler("open test.ipynb"))

    def test_ask_success(self):
        result = asyncio.run(self.handler("ask how many cells"))
        self.assertIn("Total cells: 1", result)

    def test_ask_no_question(self):
        result = asyncio.run(self.handler("ask"))
        self.assertIn("Usage", result)

    def test_ask_no_notebook(self):
        _state.clear()
        result = asyncio.run(self.handler("ask question"))
        self.assertIn("No notebook open", result)


class TestNotebookUsage(unittest.TestCase):
    def test_usage_no_sub(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["notebook"].handler(""))
        self.assertIn("Usage", result)

    def test_usage_unknown_sub(self):
        cmds = _make_registry()
        result = asyncio.run(cmds["notebook"].handler("xyz"))
        self.assertIn("Usage", result)


class TestSearchWeb(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["search"].handler
        from lidco.search.web_search import SearchResult
        _state["search_fn"] = lambda q, n: [
            SearchResult(title=f"R{i}", url=f"https://ex.com/{i}", snippet=f"S{i}")
            for i in range(n)
        ]

    def test_web_search(self):
        result = asyncio.run(self.handler("web python"))
        self.assertIn("result(s)", result)
        self.assertIn("R0", result)

    def test_web_search_no_query(self):
        result = asyncio.run(self.handler("web"))
        self.assertIn("Usage", result)

    def test_web_grounded(self):
        result = asyncio.run(self.handler("web --grounded test prompt"))
        self.assertIn("Web search context", result)
        self.assertIn("test prompt", result)

    def test_web_grounded_no_prompt(self):
        result = asyncio.run(self.handler("web --grounded"))
        self.assertIn("Usage", result)

    def test_search_usage_no_sub(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_search_usage_unknown_sub(self):
        result = asyncio.run(self.handler("xyz"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
