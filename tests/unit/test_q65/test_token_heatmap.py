"""Tests for TokenHeatmap — Q65 Task 439."""

from __future__ import annotations

import pytest


class TestTokenHeatmapRecording:
    def test_record_file_access(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_file_access("src/foo.py", 500)
        assert hm._files["src/foo.py"] == 500

    def test_record_file_accumulates(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_file_access("src/foo.py", 300)
        hm.record_file_access("src/foo.py", 200)
        assert hm._files["src/foo.py"] == 500

    def test_record_function_access(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_function_access("Foo.bar", 100)
        assert hm._functions["Foo.bar"] == 100

    def test_record_function_accumulates(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_function_access("my_fn", 50)
        hm.record_function_access("my_fn", 75)
        assert hm._functions["my_fn"] == 125


class TestTokenHeatmapQuerying:
    def test_top_files_empty(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        assert hm.top_files() == []

    def test_top_files_sorted_desc(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_file_access("a.py", 100)
        hm.record_file_access("b.py", 500)
        hm.record_file_access("c.py", 200)
        top = hm.top_files(n=2)
        assert top[0][0] == "b.py"
        assert top[1][0] == "c.py"

    def test_top_functions_sorted_desc(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        hm.record_function_access("fn_a", 10)
        hm.record_function_access("fn_b", 200)
        top = hm.top_functions(n=1)
        assert top[0][0] == "fn_b"

    def test_top_files_respects_n(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        hm = TokenHeatmap()
        for i in range(20):
            hm.record_file_access(f"file_{i}.py", i * 10)
        top = hm.top_files(n=5)
        assert len(top) == 5


class TestRenderHeatmap:
    def test_render_empty_returns_table(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        from rich.table import Table
        hm = TokenHeatmap()
        result = hm.render_heatmap([], title="Test")
        assert isinstance(result, Table)

    def test_render_with_data_returns_table(self):
        from lidco.analytics.token_heatmap import TokenHeatmap
        from rich.table import Table
        hm = TokenHeatmap()
        items = [("src/foo.py", 1000), ("src/bar.py", 500)]
        result = hm.render_heatmap(items, title="Token Heatmap")
        assert isinstance(result, Table)
