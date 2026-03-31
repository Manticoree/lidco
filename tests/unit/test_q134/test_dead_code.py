"""Tests for Q134 DeadCodeEliminator."""
from __future__ import annotations

import unittest

from lidco.transform.dead_code import DeadCodeEliminator, EliminationResult


class TestEliminationResult(unittest.TestCase):
    def test_defaults(self):
        r = EliminationResult()
        self.assertEqual(r.removed_names, [])
        self.assertEqual(r.removed_lines, 0)
        self.assertEqual(r.new_source, "")

    def test_custom_values(self):
        r = EliminationResult(removed_names=["foo"], removed_lines=3, new_source="bar")
        self.assertEqual(r.removed_names, ["foo"])
        self.assertEqual(r.removed_lines, 3)


class TestDeadCodeEliminator(unittest.TestCase):
    def setUp(self):
        self.elim = DeadCodeEliminator()

    def test_eliminate_unreachable_after_return(self):
        src = "def foo():\n    return 1\n    x = 2\n"
        result = self.elim.eliminate(src)
        self.assertNotIn("x = 2", result.new_source)
        self.assertGreater(result.removed_lines, 0)

    def test_eliminate_unreachable_after_raise(self):
        src = "def bar():\n    raise ValueError()\n    y = 3\n"
        result = self.elim.eliminate(src)
        self.assertNotIn("y = 3", result.new_source)

    def test_eliminate_unused_import(self):
        src = "import os\nx = 1\n"
        result = self.elim.eliminate(src)
        self.assertNotIn("import os", result.new_source)
        self.assertIn("os", result.removed_names)

    def test_eliminate_no_dead_code(self):
        src = "import os\nprint(os.getcwd())\n"
        result = self.elim.eliminate(src)
        self.assertIn("import os", result.new_source)
        self.assertEqual(result.removed_lines, 0)

    def test_eliminate_syntax_error(self):
        result = self.elim.eliminate("def (")
        self.assertEqual(result.new_source, "def (")

    def test_eliminate_empty_source(self):
        result = self.elim.eliminate("")
        self.assertEqual(result.removed_lines, 0)

    def test_find_dead_code_unreachable(self):
        src = "def foo():\n    return 1\n    x = 2\n"
        regions = self.elim.find_dead_code(src)
        types = [r["type"] for r in regions]
        self.assertIn("unreachable", types)

    def test_find_dead_code_unused_import(self):
        src = "import json\nx = 1\n"
        regions = self.elim.find_dead_code(src)
        types = [r["type"] for r in regions]
        self.assertIn("unused_import", types)

    def test_find_dead_code_no_dead(self):
        src = "x = 1\nprint(x)\n"
        regions = self.elim.find_dead_code(src)
        self.assertEqual(regions, [])

    def test_find_dead_code_syntax_error(self):
        self.assertEqual(self.elim.find_dead_code("def ("), [])

    def test_remove_unused_imports_basic(self):
        src = "import os\nimport sys\nprint(sys.argv)\n"
        result = self.elim.remove_unused_imports(src)
        self.assertNotIn("import os", result.new_source)
        self.assertIn("import sys", result.new_source)

    def test_remove_unused_imports_all_used(self):
        src = "import os\nprint(os.sep)\n"
        result = self.elim.remove_unused_imports(src)
        self.assertIn("import os", result.new_source)
        self.assertEqual(result.removed_lines, 0)

    def test_remove_unused_imports_syntax_error(self):
        result = self.elim.remove_unused_imports("def (")
        self.assertEqual(result.new_source, "def (")

    def test_remove_unused_imports_from_import(self):
        src = "from os import path\nx = 1\n"
        result = self.elim.remove_unused_imports(src)
        self.assertNotIn("from os import path", result.new_source)
        self.assertIn("path", result.removed_names)

    def test_eliminate_multiple_unreachable(self):
        src = "def foo():\n    return 1\n    a = 2\n    b = 3\n"
        result = self.elim.eliminate(src)
        self.assertNotIn("a = 2", result.new_source)
        self.assertNotIn("b = 3", result.new_source)

    def test_find_dead_code_has_line_info(self):
        src = "def foo():\n    return 1\n    x = 2\n"
        regions = self.elim.find_dead_code(src)
        self.assertTrue(all("line" in r for r in regions))

    def test_eliminate_preserves_reachable(self):
        src = "def foo():\n    x = 1\n    return x\n"
        result = self.elim.eliminate(src)
        self.assertIn("x = 1", result.new_source)
        self.assertIn("return x", result.new_source)

    def test_remove_unused_imports_empty(self):
        result = self.elim.remove_unused_imports("")
        self.assertEqual(result.removed_lines, 0)

    def test_eliminate_import_alias_unused(self):
        src = "import os as operating_system\nx = 1\n"
        result = self.elim.eliminate(src)
        self.assertIn("operating_system", result.removed_names)

    def test_find_dead_code_region_has_name(self):
        src = "import unused_mod\nx = 1\n"
        regions = self.elim.find_dead_code(src)
        names = [r.get("name", "") for r in regions]
        self.assertIn("unused_mod", names)


if __name__ == "__main__":
    unittest.main()
