"""OpenAPI client generator — Task 407."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Endpoint:
    """Represents a single OpenAPI endpoint."""

    method: str
    path: str
    operation_id: str
    summary: str
    params: list[dict[str, Any]]
    body_schema: dict[str, Any] | None
    response_schema: dict[str, Any] | None
    tags: list[str]


class OpenAPIParser:
    """Load and parse an OpenAPI 3.x specification.

    Supports ``.yaml``, ``.yml``, and ``.json`` files.

    Raises:
        ValueError: On unsupported format or missing spec file.
        RuntimeError: On parse errors.
    """

    def __init__(self, spec_path: str | Path) -> None:
        self._spec_path = Path(spec_path)
        self._spec: dict[str, Any] = {}

    def load(self) -> None:
        """Load and parse the spec file.

        Raises:
            ValueError: If file doesn't exist or format unsupported.
            RuntimeError: On parse error.
        """
        if not self._spec_path.exists():
            raise ValueError(f"Spec file not found: {self._spec_path}")

        suffix = self._spec_path.suffix.lower()
        content = self._spec_path.read_text(encoding="utf-8")

        if suffix in (".yaml", ".yml"):
            try:
                import yaml
                self._spec = yaml.safe_load(content)
            except ImportError:
                # Fallback: try JSON
                try:
                    self._spec = json.loads(content)
                except json.JSONDecodeError:
                    raise RuntimeError(
                        "PyYAML is not installed. Run: pip install pyyaml"
                    )
        elif suffix == ".json":
            try:
                self._spec = json.loads(content)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Failed to parse JSON spec: {exc}") from exc
        else:
            raise ValueError(
                f"Unsupported spec format: {suffix}. Use .yaml, .yml, or .json"
            )

    def load_from_dict(self, spec: dict[str, Any]) -> None:
        """Load spec from a dictionary (useful for testing).

        Args:
            spec: OpenAPI spec dictionary.
        """
        self._spec = spec

    def extract_endpoints(self) -> list[Endpoint]:
        """Extract all endpoints from the loaded spec.

        Returns:
            List of Endpoint dataclass instances.

        Raises:
            RuntimeError: If spec is not loaded or malformed.
        """
        if not self._spec:
            raise RuntimeError("Spec not loaded. Call load() first.")

        paths = self._spec.get("paths") or {}
        endpoints: list[Endpoint] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue

                params = self._extract_params(path_item, operation)
                body_schema = self._extract_body_schema(operation)
                response_schema = self._extract_response_schema(operation)

                endpoints.append(Endpoint(
                    method=method.upper(),
                    path=path,
                    operation_id=str(operation.get("operationId") or f"{method}_{path.replace('/', '_').strip('_')}"),
                    summary=str(operation.get("summary") or ""),
                    params=params,
                    body_schema=body_schema,
                    response_schema=response_schema,
                    tags=list(operation.get("tags") or []),
                ))

        return endpoints

    @property
    def spec(self) -> dict[str, Any]:
        return self._spec

    @property
    def title(self) -> str:
        return str((self._spec.get("info") or {}).get("title", "API"))

    @property
    def base_url(self) -> str:
        servers = self._spec.get("servers") or []
        if servers:
            return str(servers[0].get("url", ""))
        return ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_params(
        self, path_item: dict, operation: dict
    ) -> list[dict[str, Any]]:
        combined: list[dict] = []
        combined.extend(path_item.get("parameters") or [])
        combined.extend(operation.get("parameters") or [])
        result = []
        for p in combined:
            if isinstance(p, dict):
                result.append({
                    "name": p.get("name", ""),
                    "in": p.get("in", ""),
                    "required": bool(p.get("required", False)),
                    "schema": p.get("schema") or {},
                    "description": p.get("description", ""),
                })
        return result

    def _extract_body_schema(self, operation: dict) -> dict[str, Any] | None:
        rb = operation.get("requestBody")
        if not isinstance(rb, dict):
            return None
        content = rb.get("content") or {}
        for mime in ("application/json", "application/x-www-form-urlencoded"):
            if mime in content:
                schema = (content[mime] or {}).get("schema")
                if schema:
                    return schema
        # Take first available
        for mime_content in content.values():
            schema = (mime_content or {}).get("schema")
            if schema:
                return schema
        return None

    def _extract_response_schema(
        self, operation: dict
    ) -> dict[str, Any] | None:
        responses = operation.get("responses") or {}
        # Prefer 200/201 response
        for code in ("200", "201", "default"):
            resp = responses.get(code)
            if not isinstance(resp, dict):
                continue
            content = resp.get("content") or {}
            for mime_content in content.values():
                schema = (mime_content or {}).get("schema")
                if schema:
                    return schema
        return None


class PythonClientGenerator:
    """Generate a typed Python requests-based client from an OpenAPI spec."""

    def generate(
        self,
        parser: OpenAPIParser,
        output_file: str | Path | None = None,
    ) -> str:
        """Generate Python client code.

        Args:
            parser: A loaded OpenAPIParser instance.
            output_file: Optional path to write the generated code.

        Returns:
            Generated Python source as a string.
        """
        endpoints = parser.extract_endpoints()
        title = parser.title
        base_url = parser.base_url

        lines: list[str] = [
            '"""Auto-generated API client.',
            "",
            f"Generated from: {title}",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "import requests",
            "from typing import Any",
            "",
            "",
            f"_BASE_URL = {repr(base_url)}",
            "",
            "",
            "class APIClient:",
            f'    """Client for {title}."""',
            "",
            "    def __init__(",
            "        self,",
            "        base_url: str = _BASE_URL,",
            "        headers: dict[str, str] | None = None,",
            "    ) -> None:",
            "        self._base_url = base_url.rstrip('/')",
            "        self._session = requests.Session()",
            "        if headers:",
            "            self._session.headers.update(headers)",
            "",
        ]

        for ep in endpoints:
            lines.extend(self._generate_method(ep))

        source = "\n".join(lines) + "\n"

        if output_file:
            out_path = Path(output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(source, encoding="utf-8")

        return source

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_method(self, ep: Endpoint) -> list[str]:
        method_name = _to_snake(ep.operation_id)
        sig_parts = ["self"]

        # Path params first
        for p in ep.params:
            if p.get("in") == "path":
                sig_parts.append(f"{_safe_name(p['name'])}: str")

        # Query params
        has_query = any(p.get("in") == "query" for p in ep.params)
        if has_query:
            sig_parts.append("params: dict[str, Any] | None = None")

        # Body
        if ep.body_schema is not None:
            sig_parts.append("body: dict[str, Any] | None = None")

        sig = ", ".join(sig_parts)
        path_format = ep.path
        for p in ep.params:
            if p.get("in") == "path":
                safe = _safe_name(p["name"])
                path_format = path_format.replace(f"{{{p['name']}}}", f"{{{safe}}}")

        call_args = [
            f"f\"{{self._base_url}}{path_format}\"",
        ]
        if has_query:
            call_args.append("params=params")
        if ep.body_schema is not None:
            call_args.append("json=body")

        lines = [
            f"    def {method_name}({sig}) -> requests.Response:",
        ]
        if ep.summary:
            lines.append(f'        """{ep.summary}"""')
        lines.extend([
            f"        return self._session.{ep.method.lower()}(",
            "            " + (",\n            ".join(call_args)) + ",",
            "        )",
            "",
        ])
        return lines


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _to_snake(name: str) -> str:
    """Convert camelCase / PascalCase / kebab-case to snake_case."""
    import re
    name = re.sub(r"[-\s]", "_", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower().lstrip("_") or "operation"


def _safe_name(name: str) -> str:
    """Make a parameter name a safe Python identifier."""
    import re
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)
