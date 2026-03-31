"""Tests for MultiLanguageRepoMap — Task 929."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.ast.treesitter_parser import TreeSitterParser
from lidco.ast.universal_extractor import UniversalExtractor
from lidco.ast.repo_map import MultiLanguageRepoMap, RepoMapEntry


class TestRepoMapEntry(unittest.TestCase):
    def test_dataclass_fields(self):
        e = RepoMapEntry(file_path="a.py", language="python", line_count=10)
        self.assertEqual(e.file_path, "a.py")
        self.assertEqual(e.language, "python")
        self.assertEqual(e.symbols, [])
        self.assertEqual(e.line_count, 10)


class TestMultiLanguageRepoMap(unittest.TestCase):
    def setUp(self):
        self.parser = TreeSitterParser()
        self.extractor = UniversalExtractor(self.parser)

    def _make_walk(self, files):
        def walk_fn(root):
            return files
        return walk_fn

    def _make_read(self, contents):
        def read_fn(path):
            for key, val in contents.items():
                if path.endswith(key):
                    return val
            raise FileNotFoundError(path)
        return read_fn

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_basic(self):
        walk = self._make_walk(["app.py", "util.js"])
        read = self._make_read({
            "app.py": "def hello():\n    pass\n",
            "util.js": "function foo() {}\n",
        })
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake")
        self.assertEqual(len(entries), 2)
        langs = {e.language for e in entries}
        self.assertIn("python", langs)
        self.assertIn("javascript", langs)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_skips_unknown_ext(self):
        walk = self._make_walk(["readme.txt", "app.py"])
        read = self._make_read({"app.py": "x = 1\n"})
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].language, "python")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_respects_max_files(self):
        files = [f"f{i}.py" for i in range(20)]
        read = self._make_read({f"f{i}.py": f"x{i} = {i}\n" for i in range(20)})
        walk = self._make_walk(files)
        rmap = MultiLanguageRepoMap(self.extractor, max_files=5, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake")
        self.assertEqual(len(entries), 5)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_include_patterns(self):
        walk = self._make_walk(["app.py", "test.js", "main.go"])
        read = self._make_read({
            "app.py": "x=1\n", "test.js": "x=1\n", "main.go": "x=1\n",
        })
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake", include_patterns=["*.py"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].language, "python")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_exclude_patterns(self):
        walk = self._make_walk(["app.py", "test_foo.py"])
        read = self._make_read({"app.py": "x=1\n", "test_foo.py": "x=1\n"})
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake", exclude_patterns=["test_*"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].file_path, "app.py")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_build_handles_read_error(self):
        walk = self._make_walk(["bad.py"])
        def bad_read(path):
            raise PermissionError("nope")
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=bad_read)
        entries = rmap.build("/fake")
        self.assertEqual(len(entries), 0)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_format_map_empty(self):
        rmap = MultiLanguageRepoMap(self.extractor)
        self.assertIn("empty", rmap.format_map([]))

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_format_map_with_entries(self):
        from lidco.ast.universal_extractor import ExtractedSymbol
        entry = RepoMapEntry(
            file_path="a.py", language="python", line_count=10,
            symbols=[ExtractedSymbol(name="foo", kind="function", language="python", line=1)],
        )
        rmap = MultiLanguageRepoMap(self.extractor)
        text = rmap.format_map([entry])
        self.assertIn("a.py", text)
        self.assertIn("function", text)
        self.assertIn("foo", text)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_search_symbols(self):
        from lidco.ast.universal_extractor import ExtractedSymbol
        sym1 = ExtractedSymbol(name="fooBar", kind="function", language="python", line=1)
        sym2 = ExtractedSymbol(name="bazQux", kind="function", language="python", line=5)
        entry = RepoMapEntry(file_path="a.py", language="python", symbols=[sym1, sym2], line_count=10)
        rmap = MultiLanguageRepoMap(self.extractor)
        results = rmap.search_symbols([entry], "foo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "fooBar")

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_search_symbols_case_insensitive(self):
        from lidco.ast.universal_extractor import ExtractedSymbol
        sym = ExtractedSymbol(name="MyClass", kind="class", language="python", line=1)
        entry = RepoMapEntry(file_path="a.py", language="python", symbols=[sym], line_count=5)
        rmap = MultiLanguageRepoMap(self.extractor)
        results = rmap.search_symbols([entry], "myclass")
        self.assertEqual(len(results), 1)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_search_symbols_no_match(self):
        from lidco.ast.universal_extractor import ExtractedSymbol
        sym = ExtractedSymbol(name="abc", kind="function", language="python", line=1)
        entry = RepoMapEntry(file_path="a.py", language="python", symbols=[sym], line_count=5)
        rmap = MultiLanguageRepoMap(self.extractor)
        results = rmap.search_symbols([entry], "xyz")
        self.assertEqual(len(results), 0)

    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_line_count_calculation(self):
        walk = self._make_walk(["a.py"])
        read = self._make_read({"a.py": "line1\nline2\nline3\n"})
        rmap = MultiLanguageRepoMap(self.extractor, walk_fn=walk, read_fn=read)
        entries = rmap.build("/fake")
        self.assertEqual(entries[0].line_count, 3)


if __name__ == "__main__":
    unittest.main()
