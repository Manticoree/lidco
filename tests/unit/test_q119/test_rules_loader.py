"""Tests for RulesFileLoader — Task 727."""

from __future__ import annotations

import unittest

from lidco.rules.rules_loader import RulesFile, RulesFileLoader


class TestRulesFile(unittest.TestCase):
    """RulesFile dataclass basics."""

    def test_create_rules_file(self):
        rf = RulesFile(path="/a/b.md", glob_pattern="*.py", content="body", mtime=1.0)
        self.assertEqual(rf.path, "/a/b.md")
        self.assertEqual(rf.glob_pattern, "*.py")
        self.assertEqual(rf.content, "body")
        self.assertEqual(rf.mtime, 1.0)

    def test_default_mtime(self):
        rf = RulesFile(path="/x.md", glob_pattern="*", content="c")
        self.assertEqual(rf.mtime, 0.0)


class TestParseFrontmatter(unittest.TestCase):
    """_parse_frontmatter edge cases."""

    def _loader(self):
        return RulesFileLoader(rules_dir="/tmp/rules", listdir_fn=lambda d: [])

    def test_no_frontmatter_returns_star_and_full_content(self):
        loader = self._loader()
        glob, body = loader._parse_frontmatter("Hello world")
        self.assertEqual(glob, "*")
        self.assertEqual(body, "Hello world")

    def test_frontmatter_with_globs(self):
        loader = self._loader()
        content = '---\nglobs: "**/*.py"\n---\nBody text'
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "**/*.py")
        self.assertEqual(body, "Body text")

    def test_frontmatter_with_single_quotes(self):
        loader = self._loader()
        content = "---\nglobs: '*.js'\n---\nJS rules"
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*.js")
        self.assertEqual(body, "JS rules")

    def test_frontmatter_no_globs_field(self):
        loader = self._loader()
        content = "---\ntitle: foo\n---\nBody"
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*")
        self.assertEqual(body, "Body")

    def test_frontmatter_empty_content(self):
        loader = self._loader()
        glob, body = loader._parse_frontmatter("")
        self.assertEqual(glob, "*")
        self.assertEqual(body, "")

    def test_frontmatter_only_delimiters(self):
        loader = self._loader()
        content = "---\n---\n"
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*")
        self.assertEqual(body, "")

    def test_frontmatter_globs_no_quotes(self):
        loader = self._loader()
        content = "---\nglobs: *.txt\n---\nText rules"
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*.txt")
        self.assertEqual(body, "Text rules")

    def test_frontmatter_globs_with_spaces(self):
        loader = self._loader()
        content = '---\nglobs:   "src/**/*.py"  \n---\nPython rules'
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "src/**/*.py")
        self.assertEqual(body, "Python rules")

    def test_frontmatter_preserves_body_newlines(self):
        loader = self._loader()
        content = '---\nglobs: "*"\n---\nLine1\nLine2\nLine3'
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*")
        self.assertIn("Line1\nLine2\nLine3", body)

    def test_single_dash_line_not_frontmatter(self):
        loader = self._loader()
        content = "---\nno closing\nstuff"
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*")
        # No second ---, so no frontmatter parsed
        self.assertIn("stuff", body)

    def test_frontmatter_multiline_body(self):
        loader = self._loader()
        content = '---\nglobs: "*.md"\n---\n\nMarkdown\n\nRules here.'
        glob, body = loader._parse_frontmatter(content)
        self.assertEqual(glob, "*.md")
        self.assertIn("Markdown", body)
        self.assertIn("Rules here.", body)


class TestLoadAll(unittest.TestCase):
    """load_all with injected functions."""

    def test_loads_md_files(self):
        files = {"rule1.md": '---\nglobs: "*.py"\n---\nPython rule', "rule2.md": "Generic rule"}
        mtimes = {"rule1.md": 1.0, "rule2.md": 2.0}

        def read_fn(path):
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            return files[name]

        def listdir_fn(d):
            return list(files.keys())

        def mtime_fn(path):
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            return mtimes[name]

        loader = RulesFileLoader(rules_dir="/tmp/rules", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        result = loader.load_all()
        self.assertEqual(len(result), 2)
        globs = {r.glob_pattern for r in result}
        self.assertIn("*.py", globs)
        self.assertIn("*", globs)

    def test_ignores_non_md_files(self):
        def listdir_fn(d):
            return ["rule.md", "notes.txt", "data.json"]

        def read_fn(path):
            return "content"

        def mtime_fn(path):
            return 1.0

        loader = RulesFileLoader(rules_dir="/tmp/r", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        result = loader.load_all()
        self.assertEqual(len(result), 1)

    def test_cache_returns_same_on_same_mtime(self):
        call_count = [0]

        def read_fn(path):
            call_count[0] += 1
            return "content"

        def listdir_fn(d):
            return ["a.md"]

        def mtime_fn(path):
            return 10.0

        loader = RulesFileLoader(rules_dir="/d", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        loader.load_all()
        loader.load_all()
        self.assertEqual(call_count[0], 1)

    def test_cache_refreshes_on_mtime_change(self):
        call_count = [0]
        current_mtime = [1.0]

        def read_fn(path):
            call_count[0] += 1
            return "v2" if call_count[0] > 1 else "v1"

        def listdir_fn(d):
            return ["a.md"]

        def mtime_fn(path):
            return current_mtime[0]

        loader = RulesFileLoader(rules_dir="/d", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        r1 = loader.load_all()
        self.assertEqual(r1[0].content, "v1")

        current_mtime[0] = 2.0
        r2 = loader.load_all()
        self.assertEqual(r2[0].content, "v2")
        self.assertEqual(call_count[0], 2)

    def test_clear_cache(self):
        call_count = [0]

        def read_fn(path):
            call_count[0] += 1
            return "content"

        def listdir_fn(d):
            return ["a.md"]

        def mtime_fn(path):
            return 1.0

        loader = RulesFileLoader(rules_dir="/d", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        loader.load_all()
        loader.clear_cache()
        loader.load_all()
        self.assertEqual(call_count[0], 2)

    def test_empty_directory(self):
        loader = RulesFileLoader(rules_dir="/d", read_fn=lambda p: "", listdir_fn=lambda d: [], mtime_fn=lambda p: 0)
        result = loader.load_all()
        self.assertEqual(result, [])

    def test_listdir_error_returns_empty(self):
        def bad_listdir(d):
            raise FileNotFoundError("no such dir")

        loader = RulesFileLoader(rules_dir="/bad", read_fn=lambda p: "", listdir_fn=bad_listdir, mtime_fn=lambda p: 0)
        result = loader.load_all()
        self.assertEqual(result, [])

    def test_read_error_skips_file(self):
        def bad_read(path):
            raise OSError("cannot read")

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=bad_read,
            listdir_fn=lambda d: ["a.md"],
            mtime_fn=lambda p: 1.0,
        )
        result = loader.load_all()
        self.assertEqual(result, [])

    def test_path_is_absolute(self):
        def read_fn(path):
            return "body"

        def listdir_fn(d):
            return ["r.md"]

        def mtime_fn(path):
            return 1.0

        loader = RulesFileLoader(rules_dir="/project/rules", read_fn=read_fn, listdir_fn=listdir_fn, mtime_fn=mtime_fn)
        result = loader.load_all()
        self.assertEqual(len(result), 1)
        self.assertIn("/project/rules", result[0].path)

    def test_mtime_stored_correctly(self):
        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: "x",
            listdir_fn=lambda d: ["f.md"],
            mtime_fn=lambda p: 42.5,
        )
        result = loader.load_all()
        self.assertEqual(result[0].mtime, 42.5)

    def test_removed_file_not_in_cache(self):
        files = [["a.md", "b.md"]]

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: "x",
            listdir_fn=lambda d: files[0],
            mtime_fn=lambda p: 1.0,
        )
        r1 = loader.load_all()
        self.assertEqual(len(r1), 2)

        files[0] = ["a.md"]
        r2 = loader.load_all()
        self.assertEqual(len(r2), 1)

    def test_frontmatter_globs_in_loaded_file(self):
        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=lambda p: '---\nglobs: "tests/**"\n---\nTest rules',
            listdir_fn=lambda d: ["t.md"],
            mtime_fn=lambda p: 1.0,
        )
        result = loader.load_all()
        self.assertEqual(result[0].glob_pattern, "tests/**")
        self.assertEqual(result[0].content, "Test rules")

    def test_multiple_files_different_globs(self):
        data = {
            "py.md": ('---\nglobs: "*.py"\n---\nPython', 1.0),
            "js.md": ('---\nglobs: "*.js"\n---\nJS', 2.0),
        }

        def read_fn(path):
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            return data[name][0]

        def mtime_fn(path):
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            return data[name][1]

        loader = RulesFileLoader(
            rules_dir="/d",
            read_fn=read_fn,
            listdir_fn=lambda d: list(data.keys()),
            mtime_fn=mtime_fn,
        )
        result = loader.load_all()
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
