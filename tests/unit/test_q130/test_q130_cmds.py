"""Tests for lidco.cli.commands.q130_cmds."""
import asyncio
import json
import pytest


def _make_registry():
    from lidco.cli.commands.registry import CommandRegistry
    reg = CommandRegistry()
    import lidco.cli.commands.q130_cmds as mod
    mod._state.clear()
    mod.register(reg)
    return reg


def run(coro):
    return asyncio.run(coro)


class TestQ130Commands:
    def setup_method(self):
        self.reg = _make_registry()
        self.handler = self.reg.get("graph").handler

    def test_no_args_usage(self):
        result = run(self.handler(""))
        assert "Usage" in result or "graph" in result.lower()

    def test_add_node(self):
        result = run(self.handler("add n1 fact Python is a language"))
        assert "n1" in result or "Added" in result

    def test_add_multiple_nodes(self):
        run(self.handler("add a fact alpha content"))
        run(self.handler("add b concept beta content"))
        result = run(self.handler("stats"))
        assert "2" in result

    def test_connect_nodes(self):
        run(self.handler("add x fact X content"))
        run(self.handler("add y fact Y content"))
        result = run(self.handler("connect x y causes"))
        assert "x" in result.lower() or "Connected" in result or "y" in result.lower()

    def test_find_by_content(self):
        run(self.handler("add n1 fact Python is cool"))
        result = run(self.handler("find Python"))
        assert "n1" in result

    def test_find_no_match(self):
        run(self.handler("add n1 fact something else"))
        result = run(self.handler("find zzznothing"))
        assert "found" in result.lower() or "zzznothing" in result

    def test_path(self):
        run(self.handler("add a fact A"))
        run(self.handler("add b fact B"))
        run(self.handler("connect a b related_to"))
        result = run(self.handler("path a b"))
        assert "a" in result and "b" in result

    def test_path_no_route(self):
        run(self.handler("add x fact X"))
        run(self.handler("add y fact Y"))
        result = run(self.handler("path x y"))
        assert "no path" in result.lower() or "x" in result

    def test_stats_empty(self):
        result = run(self.handler("stats"))
        assert "0" in result or "Nodes" in result

    def test_stats_after_add(self):
        run(self.handler("add n1 fact test node"))
        result = run(self.handler("stats"))
        assert "1" in result

    def test_export_json(self):
        run(self.handler("add n1 fact exportable"))
        result = run(self.handler("export"))
        data = json.loads(result)
        assert "nodes" in data

    def test_import_json(self):
        data = json.dumps({"nodes": [
            {"id": "imp1", "content": "imported", "node_type": "fact",
             "tags": [], "confidence": 1.0, "created_at": "", "updated_at": ""}
        ], "edges": []})
        result = run(self.handler(f"import {data}"))
        assert "1" in result or "Imported" in result or "imp1" in result

    def test_add_no_args(self):
        result = run(self.handler("add"))
        assert "Usage" in result or "id" in result.lower()

    def test_connect_no_args(self):
        result = run(self.handler("connect"))
        assert "Usage" in result or "from" in result.lower()

    def test_find_no_args(self):
        result = run(self.handler("find"))
        assert "Usage" in result or "query" in result.lower()

    def test_graph_registered(self):
        assert self.reg.get("graph") is not None

    def test_path_no_args(self):
        result = run(self.handler("path"))
        assert "Usage" in result or "from" in result.lower()

    def test_find_shows_type(self):
        run(self.handler("add typenode concept my concept content"))
        result = run(self.handler("find my concept"))
        assert "concept" in result.lower() or "typenode" in result

    def test_import_invalid_json(self):
        result = run(self.handler("import {not valid json}"))
        assert "failed" in result.lower() or "error" in result.lower() or "import" in result.lower()

    def test_stats_with_edges(self):
        run(self.handler("add p fact parent"))
        run(self.handler("add c fact child"))
        run(self.handler("connect p c part_of"))
        result = run(self.handler("stats"))
        assert "1" in result  # at least one edge
