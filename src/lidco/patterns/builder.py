"""Builder pattern — fluent object construction (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


class BuilderError(Exception):
    """Raised when a builder cannot produce a valid object."""


class Builder:
    """
    Fluent builder base class.

    Subclasses define ``_required`` (list of required field names) and
    call ``self._set(field, value)`` in each ``with_*`` method.
    ``build()`` validates and returns the built object.

    Example::

        class QueryBuilder(Builder):
            _required = ["table"]

            def table(self, name: str) -> "QueryBuilder":
                return self._set("table", name)

            def where(self, clause: str) -> "QueryBuilder":
                return self._set("where", clause)

            def build(self) -> str:
                self._validate()
                where = self._data.get("where", "")
                clause = f" WHERE {where}" if where else ""
                return f"SELECT * FROM {self._data['table']}{clause}"
    """

    _required: list[str] = []

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _set(self, key: str, value: Any) -> "Builder":
        """Set a field and return self for chaining."""
        self._data = {**self._data, key: value}
        return self

    def _validate(self) -> None:
        missing = [f for f in self._required if f not in self._data]
        if missing:
            raise BuilderError(
                f"{type(self).__name__}: missing required fields: {missing}"
            )

    def reset(self) -> "Builder":
        """Reset all fields."""
        self._data = {}
        return self

    def build(self) -> Any:
        """Build and return the object.  Subclasses must override."""
        raise NotImplementedError

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


@dataclass
class HttpRequest:
    """Immutable HTTP request built by :class:`HttpRequestBuilder`."""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    timeout: float = 30.0
    params: dict[str, str] = field(default_factory=dict)


class HttpRequestBuilder(Builder):
    """Fluent builder for :class:`HttpRequest`."""

    _required = ["method", "url"]

    def method(self, value: str) -> "HttpRequestBuilder":
        return self._set("method", value.upper())  # type: ignore[return-value]

    def url(self, value: str) -> "HttpRequestBuilder":
        return self._set("url", value)  # type: ignore[return-value]

    def header(self, key: str, value: str) -> "HttpRequestBuilder":
        headers = dict(self._data.get("headers", {}))
        headers[key] = value
        return self._set("headers", headers)  # type: ignore[return-value]

    def body(self, value: str) -> "HttpRequestBuilder":
        return self._set("body", value)  # type: ignore[return-value]

    def timeout(self, seconds: float) -> "HttpRequestBuilder":
        return self._set("timeout", seconds)  # type: ignore[return-value]

    def param(self, key: str, value: str) -> "HttpRequestBuilder":
        params = dict(self._data.get("params", {}))
        params[key] = value
        return self._set("params", params)  # type: ignore[return-value]

    def get(self, url: str) -> "HttpRequestBuilder":  # type: ignore[override]
        return self.method("GET").url(url)

    def post(self, url: str) -> "HttpRequestBuilder":
        return self.method("POST").url(url)

    def build(self) -> HttpRequest:
        self._validate()
        return HttpRequest(
            method=self._data["method"],
            url=self._data["url"],
            headers=dict(self._data.get("headers", {})),
            body=self._data.get("body", ""),
            timeout=self._data.get("timeout", 30.0),
            params=dict(self._data.get("params", {})),
        )
