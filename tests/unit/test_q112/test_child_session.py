"""Tests for ChildSessionSpawner — Task 694."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from lidco.agents.child_session import (
    ChildSessionHandle,
    ChildSessionResult,
    ChildSessionSpawner,
    OutputSchema,
    SchemaValidationError,
)


class TestOutputSchema(unittest.TestCase):
    def test_creation(self):
        schema = OutputSchema(fields={"name": "str"}, required=["name"])
        self.assertEqual(schema.fields, {"name": "str"})
        self.assertEqual(schema.required, ["name"])

    def test_defaults(self):
        schema = OutputSchema(fields={"x": "int"})
        self.assertEqual(schema.required, [])

    def test_multiple_fields(self):
        schema = OutputSchema(
            fields={"a": "str", "b": "int", "c": "list"},
            required=["a", "b"],
        )
        self.assertEqual(len(schema.fields), 3)
        self.assertEqual(len(schema.required), 2)


class TestChildSessionHandle(unittest.TestCase):
    def _make_schema(self):
        return OutputSchema(
            fields={"name": "str", "count": "int"},
            required=["name"],
        )

    def test_validate_valid_json(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "prompt", schema)
        result = handle.validate(json.dumps({"name": "test", "count": 5}))
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["count"], 5)

    def test_validate_missing_required(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "prompt", schema)
        with self.assertRaises(SchemaValidationError):
            handle.validate(json.dumps({"count": 5}))

    def test_validate_wrong_type_str(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "prompt", schema)
        with self.assertRaises(SchemaValidationError):
            handle.validate(json.dumps({"name": 123}))

    def test_validate_wrong_type_int(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "prompt", schema)
        with self.assertRaises(SchemaValidationError):
            handle.validate(json.dumps({"name": "ok", "count": "not_int"}))

    def test_validate_invalid_json(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "prompt", schema)
        with self.assertRaises(SchemaValidationError):
            handle.validate("not json")

    def test_validate_list_type(self):
        schema = OutputSchema(fields={"items": "list"}, required=["items"])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({"items": [1, 2, 3]}))
        self.assertEqual(result["items"], [1, 2, 3])

    def test_validate_dict_type(self):
        schema = OutputSchema(fields={"meta": "dict"}, required=["meta"])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({"meta": {"k": "v"}}))
        self.assertEqual(result["meta"], {"k": "v"})

    def test_validate_bool_type(self):
        schema = OutputSchema(fields={"flag": "bool"}, required=["flag"])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({"flag": True}))
        self.assertTrue(result["flag"])

    def test_validate_bool_wrong_type(self):
        schema = OutputSchema(fields={"flag": "bool"}, required=["flag"])
        handle = ChildSessionHandle("s1", "p", schema)
        with self.assertRaises(SchemaValidationError):
            handle.validate(json.dumps({"flag": "yes"}))

    def test_validate_optional_field_missing(self):
        schema = OutputSchema(fields={"name": "str", "age": "int"}, required=["name"])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({"name": "Alice"}))
        self.assertEqual(result["name"], "Alice")
        self.assertNotIn("age", result)

    def test_validate_extra_fields_ignored(self):
        schema = OutputSchema(fields={"name": "str"}, required=["name"])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({"name": "ok", "extra": 999}))
        self.assertEqual(result["name"], "ok")

    def test_complete_returns_result(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "my prompt", schema)
        raw = json.dumps({"name": "test", "count": 42})
        result = handle.complete(raw)
        self.assertIsInstance(result, ChildSessionResult)
        self.assertEqual(result.session_id, "s1")
        self.assertEqual(result.prompt, "my prompt")
        self.assertEqual(result.raw_result, raw)
        self.assertEqual(result.validated["name"], "test")
        self.assertIs(result.schema, schema)

    def test_complete_raises_on_invalid(self):
        schema = self._make_schema()
        handle = ChildSessionHandle("s1", "p", schema)
        with self.assertRaises(SchemaValidationError):
            handle.complete(json.dumps({"count": 5}))

    def test_session_id_stored(self):
        handle = ChildSessionHandle("abc", "p", OutputSchema(fields={}))
        self.assertEqual(handle.session_id, "abc")

    def test_prompt_stored(self):
        handle = ChildSessionHandle("s", "hello world", OutputSchema(fields={}))
        self.assertEqual(handle.prompt, "hello world")


class TestChildSessionSpawner(unittest.TestCase):
    def test_spawn_returns_handle(self):
        spawner = ChildSessionSpawner()
        handle = spawner.spawn("Do stuff")
        self.assertIsInstance(handle, ChildSessionHandle)
        self.assertEqual(handle.prompt, "Do stuff")

    def test_spawn_unique_ids(self):
        spawner = ChildSessionSpawner()
        h1 = spawner.spawn("A")
        h2 = spawner.spawn("B")
        self.assertNotEqual(h1.session_id, h2.session_id)

    def test_spawn_with_schema(self):
        schema = OutputSchema(fields={"result": "str"}, required=["result"])
        spawner = ChildSessionSpawner()
        handle = spawner.spawn("Do stuff", schema=schema)
        self.assertIs(handle.schema, schema)

    def test_spawn_without_schema(self):
        spawner = ChildSessionSpawner()
        handle = spawner.spawn("Do stuff")
        self.assertIsNotNone(handle.schema)

    def test_spawn_and_run(self):
        schema = OutputSchema(fields={"answer": "str"}, required=["answer"])
        llm_fn = MagicMock(return_value=json.dumps({"answer": "42"}))
        spawner = ChildSessionSpawner()
        result = spawner.spawn_and_run("What is the answer?", schema, llm_fn)
        self.assertIsInstance(result, ChildSessionResult)
        self.assertEqual(result.validated["answer"], "42")
        llm_fn.assert_called_once()

    def test_spawn_and_run_validation_error(self):
        schema = OutputSchema(fields={"answer": "str"}, required=["answer"])
        llm_fn = MagicMock(return_value=json.dumps({"wrong": "key"}))
        spawner = ChildSessionSpawner()
        with self.assertRaises(SchemaValidationError):
            spawner.spawn_and_run("prompt", schema, llm_fn)

    def test_spawn_with_memory_store(self):
        store = MagicMock()
        spawner = ChildSessionSpawner(memory_store=store)
        handle = spawner.spawn("Do stuff")
        self.assertIsInstance(handle, ChildSessionHandle)

    def test_spawn_and_run_llm_fn_receives_prompt(self):
        schema = OutputSchema(fields={"x": "str"}, required=["x"])
        llm_fn = MagicMock(return_value=json.dumps({"x": "val"}))
        spawner = ChildSessionSpawner()
        spawner.spawn_and_run("my prompt", schema, llm_fn)
        llm_fn.assert_called_once_with("my prompt")

    def test_validate_empty_json_object(self):
        schema = OutputSchema(fields={"a": "str"}, required=[])
        handle = ChildSessionHandle("s1", "p", schema)
        result = handle.validate(json.dumps({}))
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
