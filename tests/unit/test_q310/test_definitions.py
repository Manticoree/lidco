"""Tests for lidco.contracts.definitions."""

import unittest

from lidco.contracts.definitions import (
    ContractDefinition,
    ContractRegistry,
    EndpointSchema,
    FieldSchema,
    FieldType,
    Role,
)


class TestFieldType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(FieldType.STRING.value, "string")
        self.assertEqual(FieldType.INTEGER.value, "integer")
        self.assertEqual(FieldType.OBJECT.value, "object")

    def test_all_members(self):
        self.assertEqual(len(FieldType), 8)


class TestRole(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Role.PROVIDER.value, "provider")
        self.assertEqual(Role.CONSUMER.value, "consumer")


class TestFieldSchema(unittest.TestCase):
    def test_basic_creation(self):
        f = FieldSchema(name="id", field_type=FieldType.INTEGER)
        self.assertEqual(f.name, "id")
        self.assertEqual(f.field_type, FieldType.INTEGER)
        self.assertTrue(f.required)

    def test_to_dict_minimal(self):
        f = FieldSchema(name="x", field_type=FieldType.STRING)
        d = f.to_dict()
        self.assertEqual(d["name"], "x")
        self.assertEqual(d["type"], "string")
        self.assertTrue(d["required"])
        self.assertNotIn("description", d)

    def test_to_dict_full(self):
        f = FieldSchema(
            name="items",
            field_type=FieldType.ARRAY,
            required=False,
            description="List of items",
            items_type=FieldType.STRING,
            default=["a"],
        )
        d = f.to_dict()
        self.assertEqual(d["items_type"], "string")
        self.assertEqual(d["description"], "List of items")
        self.assertEqual(d["default"], ["a"])

    def test_roundtrip(self):
        f = FieldSchema(
            name="data",
            field_type=FieldType.OBJECT,
            properties=(
                FieldSchema(name="nested", field_type=FieldType.BOOLEAN),
            ),
        )
        d = f.to_dict()
        f2 = FieldSchema.from_dict(d)
        self.assertEqual(f2.name, "data")
        self.assertEqual(len(f2.properties), 1)
        self.assertEqual(f2.properties[0].name, "nested")

    def test_from_dict_defaults(self):
        d = {"name": "x", "type": "integer"}
        f = FieldSchema.from_dict(d)
        self.assertTrue(f.required)
        self.assertEqual(f.description, "")
        self.assertIsNone(f.items_type)

    def test_frozen(self):
        f = FieldSchema(name="x", field_type=FieldType.STRING)
        with self.assertRaises(AttributeError):
            f.name = "y"  # type: ignore[misc]


class TestEndpointSchema(unittest.TestCase):
    def test_basic(self):
        ep = EndpointSchema(method="GET", path="/users")
        self.assertEqual(ep.method, "GET")
        self.assertEqual(ep.path, "/users")
        self.assertEqual(ep.status_code, 200)

    def test_to_dict(self):
        req = (FieldSchema(name="name", field_type=FieldType.STRING),)
        resp = (FieldSchema(name="id", field_type=FieldType.INTEGER),)
        ep = EndpointSchema(
            method="POST",
            path="/users",
            request_fields=req,
            response_fields=resp,
            description="Create user",
            status_code=201,
        )
        d = ep.to_dict()
        self.assertEqual(d["method"], "POST")
        self.assertEqual(d["status_code"], 201)
        self.assertEqual(len(d["request"]), 1)
        self.assertEqual(len(d["response"]), 1)
        self.assertEqual(d["description"], "Create user")

    def test_roundtrip(self):
        ep = EndpointSchema(
            method="DELETE",
            path="/users/{id}",
            status_code=204,
        )
        d = ep.to_dict()
        ep2 = EndpointSchema.from_dict(d)
        self.assertEqual(ep2.method, "DELETE")
        self.assertEqual(ep2.status_code, 204)

    def test_from_dict_defaults(self):
        d = {"method": "GET", "path": "/health"}
        ep = EndpointSchema.from_dict(d)
        self.assertEqual(ep.status_code, 200)
        self.assertEqual(ep.request_fields, ())
        self.assertEqual(ep.response_fields, ())


class TestContractDefinition(unittest.TestCase):
    def test_basic(self):
        c = ContractDefinition(
            name="user-api",
            version="1.0.0",
            provider="user-service",
            consumer="frontend",
        )
        self.assertEqual(c.name, "user-api")
        self.assertEqual(c.version, "1.0.0")

    def test_invalid_version(self):
        with self.assertRaises(ValueError):
            ContractDefinition(
                name="x", version="bad", provider="p", consumer="c"
            )

    def test_invalid_version_partial(self):
        with self.assertRaises(ValueError):
            ContractDefinition(
                name="x", version="1.0", provider="p", consumer="c"
            )

    def test_to_dict(self):
        c = ContractDefinition(
            name="api",
            version="2.1.0",
            provider="svc",
            consumer="web",
            metadata={"env": "test"},
        )
        d = c.to_dict()
        self.assertEqual(d["name"], "api")
        self.assertEqual(d["version"], "2.1.0")
        self.assertEqual(d["metadata"]["env"], "test")

    def test_roundtrip(self):
        ep = EndpointSchema(method="GET", path="/ping")
        c = ContractDefinition(
            name="ping",
            version="0.1.0",
            provider="p",
            consumer="c",
            endpoints=(ep,),
        )
        d = c.to_dict()
        c2 = ContractDefinition.from_dict(d)
        self.assertEqual(c2.name, "ping")
        self.assertEqual(len(c2.endpoints), 1)
        self.assertEqual(c2.endpoints[0].path, "/ping")

    def test_metadata_deep_copy(self):
        meta = {"tags": ["a"]}
        c = ContractDefinition(
            name="x", version="1.0.0", provider="p", consumer="c",
            metadata=meta,
        )
        d = c.to_dict()
        d["metadata"]["tags"].append("b")
        self.assertEqual(len(meta["tags"]), 1)


class TestContractRegistry(unittest.TestCase):
    def _make_contract(self, name="api", version="1.0.0"):
        return ContractDefinition(
            name=name, version=version, provider="prov", consumer="cons",
        )

    def test_empty(self):
        reg = ContractRegistry()
        self.assertEqual(reg.count, 0)
        self.assertEqual(reg.list_all(), [])

    def test_register(self):
        reg = ContractRegistry()
        c = self._make_contract()
        reg2 = reg.register(c)
        self.assertEqual(reg.count, 0)  # original unchanged
        self.assertEqual(reg2.count, 1)

    def test_get(self):
        reg = ContractRegistry().register(self._make_contract())
        self.assertIsNotNone(reg.get("api", "1.0.0"))
        self.assertIsNone(reg.get("api", "2.0.0"))

    def test_remove(self):
        reg = ContractRegistry().register(self._make_contract())
        reg2 = reg.remove("api", "1.0.0")
        self.assertEqual(reg.count, 1)
        self.assertEqual(reg2.count, 0)

    def test_list_versions(self):
        reg = (
            ContractRegistry()
            .register(self._make_contract(version="1.0.0"))
            .register(self._make_contract(version="2.0.0"))
        )
        self.assertEqual(reg.list_versions("api"), ["1.0.0", "2.0.0"])
        self.assertEqual(reg.list_versions("other"), [])

    def test_find_by_provider(self):
        reg = ContractRegistry().register(self._make_contract())
        self.assertEqual(len(reg.find_by_provider("prov")), 1)
        self.assertEqual(len(reg.find_by_provider("other")), 0)

    def test_find_by_consumer(self):
        reg = ContractRegistry().register(self._make_contract())
        self.assertEqual(len(reg.find_by_consumer("cons")), 1)

    def test_export_import(self):
        reg = (
            ContractRegistry()
            .register(self._make_contract(version="1.0.0"))
            .register(self._make_contract(version="1.1.0"))
        )
        data = reg.export_all()
        reg2 = ContractRegistry.import_all(data)
        self.assertEqual(reg2.count, 2)

    def test_list_all_sorted(self):
        reg = (
            ContractRegistry()
            .register(self._make_contract(name="b", version="1.0.0"))
            .register(self._make_contract(name="a", version="1.0.0"))
        )
        names = [c.name for c in reg.list_all()]
        self.assertEqual(names, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
