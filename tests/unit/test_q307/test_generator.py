"""Tests for CodeownersGenerator."""

import unittest
from unittest.mock import patch, MagicMock

from lidco.ownership.generator import (
    BlameEntry,
    CodeownersEntry,
    CodeownersGenerator,
    CodeownersResult,
    DirectoryRule,
)


class TestBlameEntry(unittest.TestCase):
    def test_frozen(self):
        be = BlameEntry(file_path="a.py", author="alice", lines=10)
        self.assertEqual(be.file_path, "a.py")
        self.assertEqual(be.author, "alice")
        self.assertEqual(be.lines, 10)
        with self.assertRaises(AttributeError):
            be.lines = 20  # type: ignore[misc]


class TestDirectoryRule(unittest.TestCase):
    def test_defaults(self):
        r = DirectoryRule(pattern="/src/", owners=["@team"])
        self.assertEqual(r.min_reviewers, 1)

    def test_frozen(self):
        r = DirectoryRule(pattern="/src/", owners=["@team"], min_reviewers=2)
        with self.assertRaises(AttributeError):
            r.pattern = "/lib/"  # type: ignore[misc]


class TestCodeownersEntry(unittest.TestCase):
    def test_to_line(self):
        entry = CodeownersEntry(pattern="/src/", owners=["@team-a", "@team-b"])
        self.assertEqual(entry.to_line(), "/src/ @team-a @team-b")

    def test_default_min_reviewers(self):
        entry = CodeownersEntry(pattern="*", owners=["@all"])
        self.assertEqual(entry.min_reviewers, 1)


class TestCodeownersResult(unittest.TestCase):
    def test_render_empty(self):
        result = CodeownersResult()
        rendered = result.render()
        self.assertIn("Auto-generated CODEOWNERS", rendered)

    def test_render_with_entries(self):
        result = CodeownersResult(
            entries=[
                CodeownersEntry(pattern="/src/", owners=["@backend"]),
                CodeownersEntry(pattern="/docs/", owners=["@docs"]),
            ],
        )
        rendered = result.render()
        self.assertIn("/src/ @backend", rendered)
        self.assertIn("/docs/ @docs", rendered)


class TestCodeownersGenerator(unittest.TestCase):
    def test_set_team_mapping_returns_new_instance(self):
        gen = CodeownersGenerator()
        gen2 = gen.set_team_mapping({"alice": "backend"})
        self.assertIsNot(gen, gen2)
        # original unchanged
        self.assertEqual(gen._team_mapping, {})
        self.assertEqual(gen2._team_mapping, {"alice": "backend"})

    def test_add_directory_rule_returns_new_instance(self):
        gen = CodeownersGenerator()
        rule = DirectoryRule(pattern="/src/", owners=["@backend"])
        gen2 = gen.add_directory_rule(rule)
        self.assertIsNot(gen, gen2)
        self.assertEqual(len(gen._directory_rules), 0)
        self.assertEqual(len(gen2._directory_rules), 1)

    def test_set_min_line_fraction(self):
        gen = CodeownersGenerator()
        gen2 = gen.set_min_line_fraction(0.25)
        self.assertAlmostEqual(gen2._min_line_fraction, 0.25)
        self.assertAlmostEqual(gen._min_line_fraction, 0.1)

    def test_generate_empty(self):
        gen = CodeownersGenerator()
        result = gen.generate([])
        self.assertEqual(len(result.entries), 0)
        self.assertEqual(len(result.unmapped_authors), 0)

    def test_generate_from_blame_entries(self):
        gen = CodeownersGenerator()
        gen = gen.set_team_mapping({"alice": "backend", "bob": "frontend"})
        entries = [
            BlameEntry(file_path="src/main.py", author="alice", lines=80),
            BlameEntry(file_path="src/main.py", author="bob", lines=20),
            BlameEntry(file_path="docs/readme.md", author="bob", lines=50),
        ]
        result = gen.generate(entries)
        self.assertGreater(len(result.entries), 0)
        self.assertEqual(len(result.unmapped_authors), 0)

    def test_generate_with_unmapped_authors(self):
        gen = CodeownersGenerator()
        entries = [
            BlameEntry(file_path="src/main.py", author="charlie", lines=100),
        ]
        result = gen.generate(entries)
        self.assertIn("charlie", result.unmapped_authors)

    def test_generate_directory_rules_take_precedence(self):
        rule = DirectoryRule(pattern="/src", owners=["@core-team"], min_reviewers=2)
        gen = CodeownersGenerator().add_directory_rule(rule)
        entries = [
            BlameEntry(file_path="src/main.py", author="alice", lines=100),
        ]
        result = gen.generate(entries)
        patterns = [e.pattern for e in result.entries]
        self.assertIn("/src", patterns)

    def test_generate_filters_by_min_line_fraction(self):
        gen = CodeownersGenerator().set_min_line_fraction(0.5)
        entries = [
            BlameEntry(file_path="src/main.py", author="alice", lines=90),
            BlameEntry(file_path="src/main.py", author="bob", lines=10),
        ]
        result = gen.generate(entries)
        # bob has < 50% so should be excluded
        for e in result.entries:
            if e.pattern.startswith("/src"):
                self.assertNotIn("@bob", e.owners)

    def test_generate_deduplicates_owners(self):
        gen = CodeownersGenerator().set_team_mapping(
            {"alice": "team", "bob": "team"},
        )
        entries = [
            BlameEntry(file_path="lib/util.py", author="alice", lines=50),
            BlameEntry(file_path="lib/util.py", author="bob", lines=50),
        ]
        result = gen.generate(entries)
        for e in result.entries:
            # Each owner label should appear only once
            self.assertEqual(len(e.owners), len(set(e.owners)))

    @patch("lidco.ownership.generator.subprocess.run")
    def test_list_tracked_files(self, mock_run):
        mock_run.return_value = MagicMock(stdout="a.py\nb.py\n")
        files = CodeownersGenerator._list_tracked_files("/repo")
        self.assertEqual(files, ["a.py", "b.py"])

    @patch("lidco.ownership.generator.subprocess.run")
    def test_list_tracked_files_error(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.SubprocessError("fail")
        files = CodeownersGenerator._list_tracked_files("/repo")
        self.assertEqual(files, [])

    @patch("lidco.ownership.generator.subprocess.run")
    def test_blame_file(self, mock_run):
        porcelain = (
            "abc123 1 1 1\n"
            "author Alice\n"
            "author-mail <alice@example.com>\n"
            "\tline content\n"
            "def456 2 2 1\n"
            "author Bob\n"
            "author-mail <bob@example.com>\n"
            "\tanother line\n"
        )
        mock_run.return_value = MagicMock(stdout=porcelain)
        entries = CodeownersGenerator._blame_file("/repo", "src/main.py")
        self.assertEqual(len(entries), 2)
        authors = {e.author for e in entries}
        self.assertEqual(authors, {"Alice", "Bob"})

    @patch("lidco.ownership.generator.subprocess.run")
    def test_blame_file_error(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.SubprocessError("fail")
        entries = CodeownersGenerator._blame_file("/repo", "src/main.py")
        self.assertEqual(entries, [])

    @patch.object(CodeownersGenerator, "_blame_file")
    @patch.object(CodeownersGenerator, "_list_tracked_files")
    def test_generate_from_git(self, mock_list, mock_blame):
        mock_list.return_value = ["src/a.py"]
        mock_blame.return_value = [
            BlameEntry(file_path="src/a.py", author="alice", lines=100),
        ]
        gen = CodeownersGenerator()
        result = gen.generate_from_git("/repo")
        self.assertGreater(len(result.entries), 0)
        mock_list.assert_called_once_with("/repo")


if __name__ == "__main__":
    unittest.main()
