"""Tests for EventSchemaRegistry (Q298)."""
import unittest

from lidco.webhooks.schemas import EventSchemaRegistry, SchemaEntry


class TestEventSchemaRegistry(unittest.TestCase):
    def _make(self):
        return EventSchemaRegistry()

    # -- register ------------------------------------------------

    def test_register_stores_schema(self):
        reg = self._make()
        reg.register("user.created", {"name": "str", "age": "int"})
        self.assertIn("user.created", reg.list_schemas())

    def test_register_overwrites_existing(self):
        reg = self._make()
        reg.register("ev", {"a": "str"})
        reg.register("ev", {"b": "int"})
        schema = reg.get_schema("ev")
        self.assertNotIn("a", schema)
        self.assertIn("b", schema)

    def test_register_with_version(self):
        reg = self._make()
        reg.register("ev", {"x": "str"}, version="2.1.0")
        self.assertEqual(reg.version("ev"), "2.1.0")

    # -- validate ------------------------------------------------

    def test_validate_valid_payload(self):
        reg = self._make()
        reg.register("ev", {"name": "str", "count": "int"})
        self.assertTrue(reg.validate("ev", {"name": "alice", "count": 5}))

    def test_validate_missing_field(self):
        reg = self._make()
        reg.register("ev", {"name": "str", "count": "int"})
        self.assertFalse(reg.validate("ev", {"name": "alice"}))

    def test_validate_wrong_type(self):
        reg = self._make()
        reg.register("ev", {"name": "str"})
        self.assertFalse(reg.validate("ev", {"name": 123}))

    def test_validate_no_schema_permissive(self):
        reg = self._make()
        self.assertTrue(reg.validate("unknown", {"anything": True}))

    def test_validate_extra_fields_ok(self):
        reg = self._make()
        reg.register("ev", {"name": "str"})
        self.assertTrue(reg.validate("ev", {"name": "a", "extra": 1}))

    # -- list_schemas --------------------------------------------

    def test_list_schemas_sorted(self):
        reg = self._make()
        reg.register("b.event", {})
        reg.register("a.event", {})
        self.assertEqual(reg.list_schemas(), ["a.event", "b.event"])

    def test_list_schemas_empty(self):
        reg = self._make()
        self.assertEqual(reg.list_schemas(), [])

    # -- version -------------------------------------------------

    def test_version_default(self):
        reg = self._make()
        reg.register("ev", {})
        self.assertEqual(reg.version("ev"), "1.0.0")

    def test_version_not_found(self):
        reg = self._make()
        self.assertEqual(reg.version("nope"), "")

    # -- get_schema ----------------------------------------------

    def test_get_schema_returns_copy(self):
        reg = self._make()
        reg.register("ev", {"a": "str"})
        s = reg.get_schema("ev")
        s["b"] = "int"
        self.assertNotIn("b", reg.get_schema("ev"))

    def test_get_schema_not_found(self):
        reg = self._make()
        self.assertIsNone(reg.get_schema("nope"))

    # -- is_compatible -------------------------------------------

    def test_compatible_same_major(self):
        self.assertTrue(EventSchemaRegistry.is_compatible("1.0.0", "1.2.0"))

    def test_compatible_same_version(self):
        self.assertTrue(EventSchemaRegistry.is_compatible("2.0.0", "2.0.0"))

    def test_incompatible_different_major(self):
        self.assertFalse(EventSchemaRegistry.is_compatible("1.0.0", "2.0.0"))

    def test_incompatible_downgrade(self):
        self.assertFalse(EventSchemaRegistry.is_compatible("1.5.0", "1.4.0"))

    def test_compatible_patch_upgrade(self):
        self.assertTrue(EventSchemaRegistry.is_compatible("1.2.3", "1.2.4"))

    # -- SchemaEntry dataclass -----------------------------------

    def test_schema_entry_defaults(self):
        entry = SchemaEntry(event_type="test", schema={"x": "str"})
        self.assertEqual(entry.version, "1.0.0")


if __name__ == "__main__":
    unittest.main()
