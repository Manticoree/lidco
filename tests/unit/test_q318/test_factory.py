"""Tests for lidco.testdata.factory (Task 1702)."""

from __future__ import annotations

import unittest

from lidco.testdata.factory import (
    DataFactory,
    FactorySchema,
    FieldSpec,
    GeneratedRecord,
    GenerationResult,
)


class TestFieldSpec(unittest.TestCase):
    def test_frozen(self) -> None:
        fs = FieldSpec("age", "int", min_value=0, max_value=120)
        with self.assertRaises(AttributeError):
            fs.name = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        fs = FieldSpec("x", "string")
        self.assertFalse(fs.nullable)
        self.assertIsNone(fs.min_value)
        self.assertIsNone(fs.choices)
        self.assertIsNone(fs.default)


class TestFactorySchema(unittest.TestCase):
    def test_field_names(self) -> None:
        schema = FactorySchema("t", (FieldSpec("a", "int"), FieldSpec("b", "string")))
        self.assertEqual(schema.field_names(), ["a", "b"])

    def test_empty_schema(self) -> None:
        schema = FactorySchema("empty")
        self.assertEqual(schema.field_names(), [])


class TestGeneratedRecord(unittest.TestCase):
    def test_get(self) -> None:
        rec = GeneratedRecord("t", {"x": 1})
        self.assertEqual(rec.get("x"), 1)
        self.assertIsNone(rec.get("missing"))
        self.assertEqual(rec.get("missing", 42), 42)

    def test_frozen(self) -> None:
        rec = GeneratedRecord("t", {})
        with self.assertRaises(AttributeError):
            rec.schema_name = "y"  # type: ignore[misc]


class TestDataFactory(unittest.TestCase):
    def _make_user_schema(self) -> FactorySchema:
        return FactorySchema("user", (
            FieldSpec("id", "int", min_value=1, max_value=99999),
            FieldSpec("name", "name"),
            FieldSpec("email", "email"),
            FieldSpec("active", "bool"),
        ))

    def test_register_and_generate_one(self) -> None:
        factory = DataFactory(seed=42).register_schema(self._make_user_schema())
        rec = factory.generate_one("user")
        self.assertEqual(rec.schema_name, "user")
        self.assertIn("id", rec.data)
        self.assertIn("name", rec.data)
        self.assertIn("email", rec.data)
        self.assertIn("@", rec.data["email"])

    def test_generate_count(self) -> None:
        factory = DataFactory(seed=7).register_schema(self._make_user_schema())
        result = factory.generate("user", count=10)
        self.assertEqual(result.count, 10)
        self.assertEqual(result.schema_name, "user")

    def test_deterministic_seed(self) -> None:
        schema = self._make_user_schema()
        f1 = DataFactory(seed=99).register_schema(schema)
        f2 = DataFactory(seed=99).register_schema(schema)
        r1 = f1.generate("user", count=3)
        r2 = f2.generate("user", count=3)
        for a, b in zip(r1.records, r2.records):
            self.assertEqual(a.data, b.data)

    def test_different_seeds_differ(self) -> None:
        schema = self._make_user_schema()
        r1 = DataFactory(seed=1).register_schema(schema).generate("user", count=3)
        r2 = DataFactory(seed=2).register_schema(schema).generate("user", count=3)
        # At least one record should differ
        any_diff = any(
            a.data != b.data for a, b in zip(r1.records, r2.records)
        )
        self.assertTrue(any_diff)

    def test_unknown_schema_raises(self) -> None:
        factory = DataFactory(seed=0)
        with self.assertRaises(ValueError):
            factory.generate("nope")

    def test_string_field(self) -> None:
        schema = FactorySchema("s", (FieldSpec("txt", "string", min_value=5),))
        rec = DataFactory(seed=1).register_schema(schema).generate_one("s")
        self.assertIsInstance(rec.data["txt"], str)
        self.assertEqual(len(rec.data["txt"]), 5)

    def test_float_field(self) -> None:
        schema = FactorySchema("f", (FieldSpec("val", "float", min_value=1.0, max_value=10.0),))
        rec = DataFactory(seed=1).register_schema(schema).generate_one("f")
        self.assertIsInstance(rec.data["val"], float)
        self.assertGreaterEqual(rec.data["val"], 1.0)
        self.assertLessEqual(rec.data["val"], 10.0)

    def test_choice_field(self) -> None:
        schema = FactorySchema("c", (
            FieldSpec("color", "choice", choices=("red", "green", "blue")),
        ))
        rec = DataFactory(seed=1).register_schema(schema).generate_one("c")
        self.assertIn(rec.data["color"], ("red", "green", "blue"))

    def test_choice_missing_choices_raises(self) -> None:
        schema = FactorySchema("c", (FieldSpec("x", "choice"),))
        with self.assertRaises(ValueError):
            DataFactory(seed=1).register_schema(schema).generate_one("c")

    def test_uuid_field(self) -> None:
        schema = FactorySchema("u", (FieldSpec("uid", "uuid"),))
        rec = DataFactory(seed=1).register_schema(schema).generate_one("u")
        self.assertRegex(rec.data["uid"], r"^[0-9a-f-]{36}$")

    def test_ref_field(self) -> None:
        addr = FactorySchema("addr", (FieldSpec("city", "string", min_value=4),))
        person = FactorySchema("person", (
            FieldSpec("name", "name"),
            FieldSpec("address", "ref", ref_factory="addr"),
        ))
        factory = DataFactory(seed=5).register_schema(addr).register_schema(person)
        rec = factory.generate_one("person")
        self.assertIsInstance(rec.data["address"], dict)
        self.assertIn("city", rec.data["address"])

    def test_ref_invalid_raises(self) -> None:
        schema = FactorySchema("bad", (FieldSpec("x", "ref", ref_factory="nope"),))
        with self.assertRaises(ValueError):
            DataFactory(seed=1).register_schema(schema).generate_one("bad")

    def test_unknown_field_type_raises(self) -> None:
        schema = FactorySchema("bad", (FieldSpec("x", "unknown_type"),))
        with self.assertRaises(ValueError):
            DataFactory(seed=1).register_schema(schema).generate_one("bad")

    def test_default_value(self) -> None:
        schema = FactorySchema("d", (FieldSpec("status", "string", default="active"),))
        rec = DataFactory(seed=1).register_schema(schema).generate_one("d")
        self.assertEqual(rec.data["status"], "active")

    def test_custom_generator(self) -> None:
        schema = FactorySchema("cg", (FieldSpec("ts", "timestamp"),))
        factory = (
            DataFactory(seed=1)
            .register_generator("timestamp", lambda rng: 1000000 + rng.randint(0, 9999))
            .register_schema(schema)
        )
        rec = factory.generate_one("cg")
        self.assertIsInstance(rec.data["ts"], int)
        self.assertGreaterEqual(rec.data["ts"], 1000000)

    def test_reset(self) -> None:
        schema = self._make_user_schema()
        factory = DataFactory(seed=42).register_schema(schema)
        r1 = factory.generate("user", count=2)
        factory2 = factory.reset()
        r2 = factory2.generate("user", count=2)
        for a, b in zip(r1.records, r2.records):
            self.assertEqual(a.data, b.data)

    def test_schemas_property(self) -> None:
        factory = DataFactory(seed=0).register_schema(self._make_user_schema())
        self.assertIn("user", factory.schemas)

    def test_seed_property(self) -> None:
        factory = DataFactory(seed=77)
        self.assertEqual(factory.seed, 77)

    def test_generation_result_frozen(self) -> None:
        gr = GenerationResult("t", (), 0)
        with self.assertRaises(AttributeError):
            gr.seed = 1  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
