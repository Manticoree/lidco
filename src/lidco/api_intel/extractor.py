"""API endpoint extraction from source code."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Endpoint:
    """A single API endpoint."""

    method: str
    path: str
    params: tuple[dict, ...] = field(default_factory=tuple)
    return_type: str = "any"
    description: str = ""


# Matches @app.get("/path"), @app.post("/path"), @router.delete("/path"), etc.
_DECORATOR_RE = re.compile(
    r'@\w+\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Matches Flask-style: @app.route("/path", methods=["GET", "POST"])
_ROUTE_RE = re.compile(
    r'@\w+\.route\(\s*["\']([^"\']+)["\']'
    r'(?:.*?methods\s*=\s*\[([^\]]*)\])?',
    re.IGNORECASE | re.DOTALL,
)

# Matches function def right after decorator
_FUNC_RE = re.compile(r'def\s+(\w+)\s*\(([^)]*)\)')

# Matches path params like {id} or <id>
_PATH_PARAM_RE = re.compile(r'[{<](\w+)[}>]')


class APIExtractor:
    """Extract API endpoints from Python source code."""

    def extract_from_source(self, source: str) -> list[Endpoint]:
        """Extract endpoints from Python source using regex on decorators."""
        endpoints: list[Endpoint] = []
        lines = source.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Try FastAPI-style decorator
            m = _DECORATOR_RE.search(line)
            if m:
                method = m.group(1).upper()
                path = m.group(2)
                params, desc = self._extract_func_info(lines, i + 1)
                path_params = self._extract_path_params(path)
                all_params = path_params + params
                endpoints = [*endpoints, Endpoint(
                    method=method,
                    path=path,
                    params=tuple(all_params),
                    description=desc,
                )]
                i += 1
                continue

            # Try Flask-style route
            m = _ROUTE_RE.search(line)
            if m:
                path = m.group(1)
                methods_str = m.group(2) or '"GET"'
                methods = [
                    s.strip().strip("'\"").upper()
                    for s in methods_str.split(",")
                    if s.strip()
                ]
                params, desc = self._extract_func_info(lines, i + 1)
                path_params = self._extract_path_params(path)
                all_params = path_params + params
                for method in methods:
                    endpoints = [*endpoints, Endpoint(
                        method=method,
                        path=path,
                        params=tuple(all_params),
                        description=desc,
                    )]
                i += 1
                continue

            i += 1

        return endpoints

    def _extract_func_info(
        self, lines: list[str], start: int,
    ) -> tuple[list[dict], str]:
        """Extract parameter info and docstring from the function after a decorator."""
        params: list[dict] = []
        desc = ""
        for j in range(start, min(start + 5, len(lines))):
            fm = _FUNC_RE.search(lines[j])
            if fm:
                func_params = fm.group(2)
                params = self._parse_func_params(func_params)
                desc = self._extract_docstring(lines, j + 1)
                break
        return params, desc

    @staticmethod
    def _parse_func_params(raw: str) -> list[dict]:
        """Parse function parameters, skipping self/request."""
        params: list[dict] = []
        skip = {"self", "request", "req", "response", "res", "db", "session"}
        for part in raw.split(","):
            part = part.strip()
            if not part or part in skip:
                continue
            # Handle type annotations: name: type = default
            name = part.split(":")[0].split("=")[0].strip()
            if name in skip or name.startswith("*"):
                continue
            type_hint = "any"
            if ":" in part:
                type_hint = part.split(":")[1].split("=")[0].strip()
            params = [*params, {"name": name, "type": type_hint, "in": "query"}]
        return params

    @staticmethod
    def _extract_docstring(lines: list[str], start: int) -> str:
        """Extract a single-line docstring if present."""
        for j in range(start, min(start + 3, len(lines))):
            stripped = lines[j].strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                quote = stripped[:3]
                if stripped.count(quote) >= 2:
                    return stripped.strip(quote[0]).strip()
                # multi-line: grab first line
                return stripped[3:].strip()
        return ""

    @staticmethod
    def _extract_path_params(path: str) -> list[dict]:
        """Extract path parameters like {id} or <id>."""
        return [
            {"name": m.group(1), "type": "string", "in": "path"}
            for m in _PATH_PARAM_RE.finditer(path)
        ]

    @staticmethod
    def to_openapi(endpoints: list[Endpoint], title: str = "API") -> dict:
        """Generate an OpenAPI 3.0 skeleton from endpoints."""
        paths: dict = {}
        for ep in endpoints:
            path_key = ep.path
            if path_key not in paths:
                paths[path_key] = {}
            operation: dict = {"summary": ep.description or ep.path}
            if ep.params:
                parameters = []
                for p in ep.params:
                    parameters = [*parameters, {
                        "name": p["name"],
                        "in": p.get("in", "query"),
                        "schema": {"type": p.get("type", "string")},
                    }]
                operation["parameters"] = parameters
            operation["responses"] = {
                "200": {"description": "Successful response"},
            }
            paths[path_key][ep.method.lower()] = operation

        return {
            "openapi": "3.0.0",
            "info": {"title": title, "version": "1.0.0"},
            "paths": paths,
        }

    @staticmethod
    def to_graphql_schema(endpoints: list[Endpoint]) -> str:
        """Generate a basic GraphQL schema string from endpoints."""
        queries: list[str] = []
        mutations: list[str] = []
        for ep in endpoints:
            name = ep.path.strip("/").replace("/", "_").replace("{", "").replace("}", "").replace("-", "_")
            if not name:
                name = "root"
            args = ""
            if ep.params:
                arg_parts = [f"{p['name']}: String" for p in ep.params]
                args = f"({', '.join(arg_parts)})"
            line = f"  {name}{args}: JSON"
            if ep.method.upper() in ("GET",):
                queries.append(line)
            else:
                mutations.append(line)

        parts: list[str] = []
        if queries:
            parts.append("type Query {\n" + "\n".join(queries) + "\n}")
        if mutations:
            parts.append("type Mutation {\n" + "\n".join(mutations) + "\n}")
        if not parts:
            return "type Query {\n  _empty: String\n}"
        return "\n\n".join(parts)

    @staticmethod
    def summary(endpoints: list[Endpoint]) -> str:
        """Return a human-readable summary of endpoints."""
        if not endpoints:
            return "No endpoints found."
        lines = [f"Found {len(endpoints)} endpoint(s):"]
        for ep in endpoints:
            desc = f" — {ep.description}" if ep.description else ""
            params_str = ""
            if ep.params:
                params_str = f" [{len(ep.params)} param(s)]"
            lines.append(f"  {ep.method} {ep.path}{params_str}{desc}")
        return "\n".join(lines)
