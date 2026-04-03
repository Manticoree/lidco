"""Tests for APIExtractor (Q256)."""
from __future__ import annotations

import unittest

from lidco.api_intel.extractor import APIExtractor, Endpoint


FASTAPI_SOURCE = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users(skip: int, limit: int):
    """List all users."""
    pass

@app.post("/users")
def create_user(name: str, email: str):
    """Create a new user."""
    pass

@app.get("/users/{user_id}")
def get_user(user_id: int):
    """Get a user by ID."""
    pass

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    pass

@app.put("/users/{user_id}")
def update_user(user_id: int, name: str):
    pass
'''

FLASK_SOURCE = '''
from flask import Flask
app = Flask(__name__)

@app.route("/items", methods=["GET"])
def list_items():
    """List items."""
    pass

@app.route("/items", methods=["POST"])
def create_item():
    """Create item."""
    pass

@app.route("/items/<item_id>", methods=["GET", "DELETE"])
def manage_item(item_id):
    """Manage an item."""
    pass
'''


class TestEndpoint(unittest.TestCase):
    def test_frozen(self):
        ep = Endpoint(method="GET", path="/test")
        with self.assertRaises(AttributeError):
            ep.method = "POST"  # type: ignore[misc]

    def test_defaults(self):
        ep = Endpoint(method="GET", path="/x")
        self.assertEqual(ep.params, ())
        self.assertEqual(ep.return_type, "any")
        self.assertEqual(ep.description, "")

    def test_equality(self):
        a = Endpoint(method="GET", path="/a")
        b = Endpoint(method="GET", path="/a")
        self.assertEqual(a, b)


class TestExtractFastAPI(unittest.TestCase):
    def setUp(self):
        self.ext = APIExtractor()
        self.endpoints = self.ext.extract_from_source(FASTAPI_SOURCE)

    def test_count(self):
        self.assertEqual(len(self.endpoints), 5)

    def test_methods(self):
        methods = [ep.method for ep in self.endpoints]
        self.assertIn("GET", methods)
        self.assertIn("POST", methods)
        self.assertIn("DELETE", methods)
        self.assertIn("PUT", methods)

    def test_paths(self):
        paths = [ep.path for ep in self.endpoints]
        self.assertIn("/users", paths)
        self.assertIn("/users/{user_id}", paths)

    def test_get_users_params(self):
        ep = [e for e in self.endpoints if e.path == "/users" and e.method == "GET"][0]
        names = [p["name"] for p in ep.params]
        self.assertIn("skip", names)
        self.assertIn("limit", names)

    def test_path_params_extracted(self):
        ep = [e for e in self.endpoints if e.path == "/users/{user_id}" and e.method == "GET"][0]
        path_params = [p for p in ep.params if p["in"] == "path"]
        self.assertEqual(len(path_params), 1)
        self.assertEqual(path_params[0]["name"], "user_id")

    def test_description_extracted(self):
        ep = [e for e in self.endpoints if e.path == "/users" and e.method == "GET"][0]
        self.assertEqual(ep.description, "List all users.")


class TestExtractFlask(unittest.TestCase):
    def setUp(self):
        self.ext = APIExtractor()
        self.endpoints = self.ext.extract_from_source(FLASK_SOURCE)

    def test_count(self):
        # /items GET, /items POST, /items/<item_id> GET, /items/<item_id> DELETE
        self.assertEqual(len(self.endpoints), 4)

    def test_flask_path_params(self):
        eps = [e for e in self.endpoints if "<item_id>" in e.path]
        self.assertTrue(len(eps) >= 1)
        path_params = [p for p in eps[0].params if p["in"] == "path"]
        self.assertEqual(path_params[0]["name"], "item_id")


class TestExtractEmpty(unittest.TestCase):
    def test_no_endpoints(self):
        ext = APIExtractor()
        self.assertEqual(ext.extract_from_source("x = 1"), [])

    def test_empty_source(self):
        ext = APIExtractor()
        self.assertEqual(ext.extract_from_source(""), [])


class TestToOpenAPI(unittest.TestCase):
    def setUp(self):
        self.ext = APIExtractor()
        self.endpoints = self.ext.extract_from_source(FASTAPI_SOURCE)

    def test_structure(self):
        spec = APIExtractor.to_openapi(self.endpoints, title="MyAPI")
        self.assertEqual(spec["openapi"], "3.0.0")
        self.assertEqual(spec["info"]["title"], "MyAPI")
        self.assertIn("paths", spec)

    def test_paths_present(self):
        spec = APIExtractor.to_openapi(self.endpoints)
        self.assertIn("/users", spec["paths"])
        self.assertIn("/users/{user_id}", spec["paths"])

    def test_methods_in_path(self):
        spec = APIExtractor.to_openapi(self.endpoints)
        self.assertIn("get", spec["paths"]["/users"])
        self.assertIn("post", spec["paths"]["/users"])

    def test_empty_endpoints(self):
        spec = APIExtractor.to_openapi([])
        self.assertEqual(spec["paths"], {})


class TestToGraphQL(unittest.TestCase):
    def test_queries_for_get(self):
        eps = [Endpoint(method="GET", path="/items")]
        schema = APIExtractor.to_graphql_schema(eps)
        self.assertIn("type Query", schema)
        self.assertIn("items", schema)

    def test_mutations_for_post(self):
        eps = [Endpoint(method="POST", path="/items")]
        schema = APIExtractor.to_graphql_schema(eps)
        self.assertIn("type Mutation", schema)

    def test_empty(self):
        schema = APIExtractor.to_graphql_schema([])
        self.assertIn("type Query", schema)
        self.assertIn("_empty", schema)

    def test_params_in_schema(self):
        eps = [Endpoint(method="GET", path="/items", params=({"name": "q", "type": "string"},))]
        schema = APIExtractor.to_graphql_schema(eps)
        self.assertIn("q: String", schema)


class TestSummary(unittest.TestCase):
    def test_no_endpoints(self):
        self.assertEqual(APIExtractor.summary([]), "No endpoints found.")

    def test_with_endpoints(self):
        eps = [Endpoint(method="GET", path="/x", description="Get X")]
        s = APIExtractor.summary(eps)
        self.assertIn("1 endpoint(s)", s)
        self.assertIn("GET /x", s)
        self.assertIn("Get X", s)

    def test_params_count(self):
        eps = [Endpoint(method="GET", path="/y", params=({"name": "a"},))]
        s = APIExtractor.summary(eps)
        self.assertIn("1 param(s)", s)


if __name__ == "__main__":
    unittest.main()
