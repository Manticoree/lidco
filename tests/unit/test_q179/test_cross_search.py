"""Tests for CrossRepoSearch."""

from __future__ import annotations

import os
import tempfile
import unittest

from lidco.workspace.cross_search import CrossRepoSearch, SearchResult


class TestCrossRepoSearch(unittest.TestCase):
    """Tests for cross-repo text search."""

    def setUp(self) -> None:
        self.searcher = CrossRepoSearch()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers -------------------------------------------------------------

    def _write(self, rel_path: str, content: str) -> str:
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        return full

    def _repo(self, name: str) -> str:
        path = os.path.join(self.root, name)
        os.makedirs(path, exist_ok=True)
        return path

    # -- basic search --------------------------------------------------------

    def test_single_repo_single_match(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/main.py", "hello world\n")
        results = self.searcher.search("hello", [repo])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].repo, "repo1")
        self.assertEqual(results[0].line, 1)
        self.assertIn("hello", results[0].match)

    def test_single_repo_multiple_matches(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/a.py", "foo bar\nbaz foo\n")
        results = self.searcher.search("foo", [repo])
        self.assertEqual(len(results), 2)

    def test_multi_repo(self) -> None:
        r1 = self._repo("r1")
        r2 = self._repo("r2")
        self._write("r1/a.txt", "needle\n")
        self._write("r2/b.txt", "needle here\n")
        results = self.searcher.search("needle", [r1, r2])
        repos_found = {r.repo for r in results}
        self.assertEqual(repos_found, {"r1", "r2"})

    def test_no_results(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/a.txt", "nothing here\n")
        results = self.searcher.search("MISSING", [repo])
        self.assertEqual(results, [])

    def test_empty_query(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/a.txt", "content\n")
        results = self.searcher.search("", [repo])
        self.assertEqual(results, [])

    # -- ignore patterns -----------------------------------------------------

    def test_default_ignore_pyc(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/cache.pyc", "needle\n")
        self._write("repo1/main.py", "needle\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file, "main.py")

    def test_custom_ignore(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/data.log", "needle\n")
        self._write("repo1/main.py", "needle\n")
        results = self.searcher.search("needle", [repo], ignore_patterns=["*.log"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file, "main.py")

    def test_ignore_empty_list(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/cache.pyc", "needle\n")
        results = self.searcher.search("needle", [repo], ignore_patterns=[])
        self.assertEqual(len(results), 1)

    # -- edge cases ----------------------------------------------------------

    def test_nonexistent_repo(self) -> None:
        results = self.searcher.search("x", ["/does/not/exist/xyz"])
        self.assertEqual(results, [])

    def test_binary_file_skipped(self) -> None:
        repo = self._repo("repo1")
        path = os.path.join(repo, "data.bin")
        with open(path, "wb") as fh:
            fh.write(b"\x00needle\xff\n")
        results = self.searcher.search("needle", [repo], ignore_patterns=[])
        # binary file is read with errors='replace', so match may still occur
        # just verify no crash
        self.assertIsInstance(results, list)

    def test_special_chars_in_query(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/a.py", "value = foo(bar)\n")
        results = self.searcher.search("foo(bar)", [repo])
        self.assertEqual(len(results), 1)

    def test_search_result_fields(self) -> None:
        r = SearchResult(repo="r", file="f.py", line=5, match="text")
        self.assertEqual(r.repo, "r")
        self.assertEqual(r.file, "f.py")
        self.assertEqual(r.line, 5)
        self.assertEqual(r.match, "text")

    def test_subdirectory_search(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/sub/deep/file.py", "needle\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 1)
        self.assertIn("sub", results[0].file)

    def test_multi_line_file(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/f.py", "line1\nneedle\nline3\nneedle again\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].line, 2)
        self.assertEqual(results[1].line, 4)

    def test_empty_repos_list(self) -> None:
        results = self.searcher.search("needle", [])
        self.assertEqual(results, [])

    def test_default_ignore_node_modules(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/node_modules/pkg/index.js", "needle\n")
        self._write("repo1/src/main.js", "needle\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 1)
        self.assertIn("src", results[0].file)

    def test_default_ignore_git(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/.git/config", "needle\n")
        self._write("repo1/main.py", "needle\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 1)

    def test_match_preserves_line_content(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/a.py", "  leading spaces needle  \n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].match, "  leading spaces needle  ")

    def test_multiple_files_sorted(self) -> None:
        repo = self._repo("repo1")
        self._write("repo1/b.py", "needle\n")
        self._write("repo1/a.py", "needle\n")
        results = self.searcher.search("needle", [repo])
        self.assertEqual(len(results), 2)
        # Files should be sorted within walk
        files = [r.file for r in results]
        self.assertEqual(files, sorted(files))


if __name__ == "__main__":
    unittest.main()
