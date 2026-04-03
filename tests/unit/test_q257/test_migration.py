"""Tests for lidco.types.migration — TypeMigration."""
from __future__ import annotations

import unittest

from lidco.types.migration import MigrationRule, TypeMigration


class TestMigrationRule(unittest.TestCase):
    def test_frozen(self):
        r = MigrationRule(pattern="a", replacement="b", description="test")
        with self.assertRaises(AttributeError):
            r.pattern = "c"  # type: ignore[misc]


class TestWithDefaults(unittest.TestCase):
    def test_has_rules(self):
        m = TypeMigration.with_defaults()
        rules = m.list_rules()
        self.assertGreater(len(rules), 0)

    def test_includes_pep604(self):
        m = TypeMigration.with_defaults()
        descriptions = [r.description for r in m.list_rules()]
        self.assertTrue(any("PEP 604" in d for d in descriptions))

    def test_includes_pep585(self):
        m = TypeMigration.with_defaults()
        descriptions = [r.description for r in m.list_rules()]
        self.assertTrue(any("PEP 585" in d for d in descriptions))


class TestApply(unittest.TestCase):
    def setUp(self):
        self.m = TypeMigration.with_defaults()

    def test_optional_to_union(self):
        src = "def foo(x: Optional[int]) -> None: ..."
        result = self.m.apply(src)
        self.assertIn("int | None", result)
        self.assertNotIn("Optional", result)

    def test_union_to_pipe(self):
        src = "def foo(x: Union[int, str]) -> None: ..."
        result = self.m.apply(src)
        self.assertIn("int | str", result)
        self.assertNotIn("Union", result)

    def test_dict_lowercase(self):
        src = "x: Dict[str, int] = {}"
        result = self.m.apply(src)
        self.assertIn("dict[str, int]", result)
        self.assertNotIn("Dict[", result)

    def test_list_lowercase(self):
        src = "x: List[int] = []"
        result = self.m.apply(src)
        self.assertIn("list[int]", result)

    def test_tuple_lowercase(self):
        src = "x: Tuple[int, str] = (1, 'a')"
        result = self.m.apply(src)
        self.assertIn("tuple[int, str]", result)

    def test_set_lowercase(self):
        src = "x: Set[int] = set()"
        result = self.m.apply(src)
        self.assertIn("set[int]", result)

    def test_frozenset_lowercase(self):
        src = "x: FrozenSet[int] = frozenset()"
        result = self.m.apply(src)
        self.assertIn("frozenset[int]", result)

    def test_type_lowercase(self):
        src = "x: Type[Foo] = Foo"
        result = self.m.apply(src)
        self.assertIn("type[Foo]", result)

    def test_no_change_when_modern(self):
        src = "x: dict[str, int] = {}"
        result = self.m.apply(src)
        self.assertEqual(result, src)

    def test_multiple_rules_applied(self):
        src = "def f(x: Optional[List[int]]) -> Dict[str, str]: ..."
        result = self.m.apply(src)
        self.assertNotIn("Optional", result)
        self.assertIn("list[", result)
        self.assertIn("dict[", result)


class TestApplyRule(unittest.TestCase):
    def test_custom_rule(self):
        rule = MigrationRule(pattern=r"\bAny\b", replacement="object", description="Any -> object")
        result = TypeMigration.apply_rule("x: Any = 1", rule)
        self.assertIn("object", result)
        self.assertNotIn("Any", result)


class TestPreview(unittest.TestCase):
    def setUp(self):
        self.m = TypeMigration.with_defaults()

    def test_preview_shows_changes(self):
        src = "x: Optional[int] = None"
        changes = self.m.preview(src)
        self.assertGreater(len(changes), 0)
        self.assertIn("description", changes[0])

    def test_preview_empty_when_no_change(self):
        src = "x: int = 5"
        changes = self.m.preview(src)
        self.assertEqual(changes, [])


class TestListRules(unittest.TestCase):
    def test_returns_copy(self):
        m = TypeMigration.with_defaults()
        rules1 = m.list_rules()
        rules2 = m.list_rules()
        self.assertEqual(len(rules1), len(rules2))
        self.assertIsNot(rules1, rules2)

    def test_empty_migration(self):
        m = TypeMigration()
        self.assertEqual(m.list_rules(), [])


if __name__ == "__main__":
    unittest.main()
