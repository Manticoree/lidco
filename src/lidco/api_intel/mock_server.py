"""In-memory API mock server for testing."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.api_intel.extractor import Endpoint


@dataclass
class MockResponse:
    """A mock HTTP response."""

    status: int = 200
    body: dict = field(default_factory=dict)
    delay_ms: int = 0


class APIMockServer:
    """In-memory mock server that stores routes and returns mock responses."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], MockResponse] = {}
        self._hit_counts: dict[tuple[str, str], int] = {}

    def add_route(
        self,
        method: str,
        path: str,
        response: MockResponse,
    ) -> None:
        """Register a mock route."""
        key = (method.upper(), path)
        self._routes = {**self._routes, key: response}
        if key not in self._hit_counts:
            self._hit_counts = {**self._hit_counts, key: 0}

    def get_response(self, method: str, path: str) -> MockResponse | None:
        """Look up the mock response for a given method+path."""
        key = (method.upper(), path)
        resp = self._routes.get(key)
        if resp is not None:
            self._hit_counts = {
                **self._hit_counts,
                key: self._hit_counts.get(key, 0) + 1,
            }
        return resp

    def list_routes(self) -> list[dict]:
        """List all registered routes."""
        routes: list[dict] = []
        for (method, path), resp in self._routes.items():
            routes = [*routes, {
                "method": method,
                "path": path,
                "status": resp.status,
                "hits": self._hit_counts.get((method, path), 0),
            }]
        return routes

    def generate_from_endpoints(self, endpoints: list[Endpoint]) -> None:
        """Auto-create mock routes from extracted endpoints."""
        for ep in endpoints:
            body = self._generate_body(ep)
            self.add_route(ep.method, ep.path, MockResponse(
                status=200,
                body=body,
            ))

    @staticmethod
    def _generate_body(ep: Endpoint) -> dict:
        """Generate a plausible mock response body for an endpoint."""
        name = ep.path.strip("/").split("/")[-1] if "/" in ep.path else "data"
        name = name.replace("{", "").replace("}", "").replace("-", "_")
        if not name:
            name = "data"
        if ep.method.upper() == "DELETE":
            return {"deleted": True}
        if ep.method.upper() == "POST":
            return {"id": 1, "created": True}
        return {name: "mock_value"}

    def stats(self) -> dict:
        """Return stats about the mock server."""
        total_hits = sum(self._hit_counts.values())
        return {
            "total_routes": len(self._routes),
            "total_hits": total_hits,
            "routes": self.list_routes(),
        }
