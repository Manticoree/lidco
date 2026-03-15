"""Tests for Q60/407 — OpenAPI client generator."""
from __future__ import annotations
import pytest
import json
from pathlib import Path
from lidco.integrations.openapi_gen import OpenAPIParser, Endpoint, PythonClientGenerator


SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List users",
                "tags": ["users"],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createUser",
                "summary": "Create user",
                "tags": ["users"],
                "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get user",
                "tags": ["users"],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}


class TestOpenAPIParser:
    def test_instantiates(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        assert p is not None

    def test_load_and_extract(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        endpoints = p.extract_endpoints()
        assert len(endpoints) >= 3

    def test_endpoint_dataclass(self):
        e = Endpoint(method="GET", path="/users", operation_id="listUsers",
                     summary="List users", params=[], body_schema=None, response_schema=None, tags=[])
        assert e.method == "GET"
        assert e.path == "/users"

    def test_load_from_dict(self, tmp_path):
        spec_file = tmp_path / "dummy.json"
        spec_file.write_text("{}")
        p = OpenAPIParser(str(spec_file))
        p.load_from_dict(SAMPLE_SPEC)
        endpoints = p.extract_endpoints()
        assert len(endpoints) >= 3

    def test_missing_file_raises(self, tmp_path):
        spec_file = tmp_path / "nonexistent.yaml"
        p = OpenAPIParser(str(spec_file))
        with pytest.raises((ValueError, Exception)):
            p.load()

    def test_methods_extracted(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        endpoints = p.extract_endpoints()
        methods = {e.method for e in endpoints}
        assert "GET" in methods
        assert "POST" in methods

    def test_paths_extracted(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        endpoints = p.extract_endpoints()
        paths = {e.path for e in endpoints}
        assert "/users" in paths

    def test_params_extracted(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        endpoints = p.extract_endpoints()
        id_endpoints = [e for e in endpoints if "{id}" in e.path]
        assert len(id_endpoints) >= 1
        assert len(id_endpoints[0].params) >= 1

    def test_title_property(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        assert "Test API" in p.title


class TestPythonClientGenerator:
    def test_instantiates(self):
        g = PythonClientGenerator()
        assert g is not None

    def test_generate_returns_string(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        g = PythonClientGenerator()
        code = g.generate(p)
        assert isinstance(code, str)

    def test_generated_contains_class(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        g = PythonClientGenerator()
        code = g.generate(p)
        assert "class " in code or "def " in code

    def test_generate_writes_file(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        g = PythonClientGenerator()
        output = tmp_path / "client.py"
        g.generate(p, str(output))
        assert output.exists()

    def test_generated_contains_imports(self, tmp_path):
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(SAMPLE_SPEC))
        p = OpenAPIParser(str(spec_file))
        p.load()
        g = PythonClientGenerator()
        code = g.generate(p)
        assert "import" in code
