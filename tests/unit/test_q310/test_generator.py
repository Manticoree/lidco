"""Tests for lidco.contracts.generator."""

import json
import unittest

from lidco.contracts.definitions import FieldType
from lidco.contracts.generator import (
    ContractGenerator,
    RecordedInteraction,
    _infer_field_type,
    _infer_fields,
)


class TestRecordedInteraction(unittest.TestCase):
    def test_defaults(self):
        ix = RecordedInteraction(method="GET", path="/api")
        self.assertEqual(ix.method, "GET")
        self.assertEqual(ix.status_code, 200)
        self.assertEqual(ix.request_body, {})
        self.assertEqual(ix.response_body, {})

    def test_interaction_id_stable(self):
        ix = RecordedInteraction(method="GET", path="/api")
        id1 = ix.interaction_id()
        id2 = ix.interaction_id()
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 12)

    def test_interaction_id_differs(self):
        ix1 = RecordedInteraction(method="GET", path="/a")
        ix2 = RecordedInteraction(method="POST", path="/a")
        self.assertNotEqual(ix1.interaction_id(), ix2.interaction_id())

    def test_frozen(self):
        ix = RecordedInteraction(method="GET", path="/x")
        with self.assertRaises(AttributeError):
            ix.method = "POST"  # type: ignore[misc]


class TestInferFieldType(unittest.TestCase):
    def test_string(self):
        self.assertEqual(_infer_field_type("hello"), FieldType.STRING)

    def test_integer(self):
        self.assertEqual(_infer_field_type(42), FieldType.INTEGER)

    def test_float(self):
        self.assertEqual(_infer_field_type(3.14), FieldType.FLOAT)

    def test_boolean(self):
        self.assertEqual(_infer_field_type(True), FieldType.BOOLEAN)

    def test_list(self):
        self.assertEqual(_infer_field_type([1, 2]), FieldType.ARRAY)

    def test_tuple(self):
        self.assertEqual(_infer_field_type((1, 2)), FieldType.ARRAY)

    def test_dict(self):
        self.assertEqual(_infer_field_type({"a": 1}), FieldType.OBJECT)

    def test_none(self):
        self.assertEqual(_infer_field_type(None), FieldType.NULL)

    def test_unknown(self):
        self.assertEqual(_infer_field_type(object()), FieldType.ANY)


class TestInferFields(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_infer_fields({}), ())

    def test_simple(self):
        fields = _infer_fields({"name": "alice", "age": 30})
        self.assertEqual(len(fields), 2)
        names = {f.name for f in fields}
        self.assertEqual(names, {"name", "age"})

    def test_nested_object(self):
        fields = _infer_fields({"data": {"key": "val"}})
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].field_type, FieldType.OBJECT)
        self.assertEqual(len(fields[0].properties), 1)

    def test_array_with_items(self):
        fields = _infer_fields({"tags": ["a", "b"]})
        self.assertEqual(fields[0].items_type, FieldType.STRING)

    def test_empty_array(self):
        fields = _infer_fields({"items": []})
        self.assertIsNone(fields[0].items_type)

    def test_sorted_output(self):
        fields = _infer_fields({"z": 1, "a": 2, "m": 3})
        names = [f.name for f in fields]
        self.assertEqual(names, ["a", "m", "z"])


class TestContractGenerator(unittest.TestCase):
    def test_empty_generator(self):
        gen = ContractGenerator()
        self.assertEqual(gen.interaction_count, 0)

    def test_record(self):
        gen = ContractGenerator()
        ix = RecordedInteraction(method="GET", path="/api")
        gen.record(ix)
        self.assertEqual(gen.interaction_count, 1)

    def test_clear(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(method="GET", path="/api"))
        gen.clear()
        self.assertEqual(gen.interaction_count, 0)

    def test_generate_empty(self):
        gen = ContractGenerator()
        contract = gen.generate("api", "1.0.0", "svc", "web")
        self.assertEqual(contract.name, "api")
        self.assertEqual(len(contract.endpoints), 0)

    def test_generate_with_interactions(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(
            method="GET", path="/users",
            response_body={"id": 1, "name": "alice"},
        ))
        gen.record(RecordedInteraction(
            method="POST", path="/users",
            request_body={"name": "bob"},
            response_body={"id": 2},
            status_code=201,
        ))
        contract = gen.generate("user-api", "1.0.0", "user-svc", "frontend")
        self.assertEqual(len(contract.endpoints), 2)
        self.assertEqual(contract.provider, "user-svc")

    def test_generate_deduplicates(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(method="GET", path="/x"))
        gen.record(RecordedInteraction(method="GET", path="/x"))
        contract = gen.generate("api", "1.0.0", "p", "c")
        self.assertEqual(len(contract.endpoints), 1)

    def test_to_pact(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(
            method="GET", path="/health",
            response_body={"status": "ok"},
            description="Health check",
        ))
        pact = gen.to_pact("my-svc", "client")
        self.assertEqual(pact["provider"]["name"], "my-svc")
        self.assertEqual(pact["consumer"]["name"], "client")
        self.assertEqual(len(pact["interactions"]), 1)
        ix = pact["interactions"][0]
        self.assertEqual(ix["description"], "Health check")
        self.assertEqual(ix["request"]["method"], "GET")
        self.assertEqual(ix["response"]["status"], 200)
        self.assertEqual(pact["metadata"]["pactSpecification"]["version"], "2.0.0")

    def test_to_pact_empty(self):
        gen = ContractGenerator()
        pact = gen.to_pact("p", "c")
        self.assertEqual(pact["interactions"], [])

    def test_to_pact_no_body(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(method="DELETE", path="/x"))
        pact = gen.to_pact("p", "c")
        ix = pact["interactions"][0]
        self.assertIsNone(ix["request"]["body"])
        self.assertIsNone(ix["response"]["body"])

    def test_to_json(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(
            method="GET", path="/api",
            response_body={"ok": True},
        ))
        raw = gen.to_json("api", "1.0.0", "p", "c")
        data = json.loads(raw)
        self.assertEqual(data["name"], "api")
        self.assertEqual(data["version"], "1.0.0")

    def test_generate_infers_response_fields(self):
        gen = ContractGenerator()
        gen.record(RecordedInteraction(
            method="GET", path="/data",
            response_body={"count": 5, "items": [1, 2]},
        ))
        contract = gen.generate("api", "1.0.0", "p", "c")
        ep = contract.endpoints[0]
        field_names = {f.name for f in ep.response_fields}
        self.assertIn("count", field_names)
        self.assertIn("items", field_names)


if __name__ == "__main__":
    unittest.main()
