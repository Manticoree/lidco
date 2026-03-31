"""HTTP request/response data models and a fluent request builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class HttpRequest:
    """Represents an outgoing HTTP request."""

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[Union[str, bytes]] = None
    timeout: float = 30.0


@dataclass
class HttpResponse:
    """Represents an incoming HTTP response."""

    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class RequestBuilder:
    """Fluent builder for ``HttpRequest`` objects."""

    def __init__(self) -> None:
        self._method: str = "GET"
        self._url: str = ""
        self._headers: dict[str, str] = {}
        self._body: Optional[Union[str, bytes]] = None
        self._timeout: float = 30.0

    # --- fluent setters ---

    def method(self, m: str) -> "RequestBuilder":
        self._method = m.upper()
        return self

    def url(self, u: str) -> "RequestBuilder":
        self._url = u
        return self

    def header(self, k: str, v: str) -> "RequestBuilder":
        self._headers[k] = v
        return self

    def body(self, b: Optional[Union[str, bytes]]) -> "RequestBuilder":
        self._body = b
        return self

    def timeout(self, t: float) -> "RequestBuilder":
        self._timeout = t
        return self

    def build(self) -> HttpRequest:
        """Construct the ``HttpRequest``."""
        return HttpRequest(
            method=self._method,
            url=self._url,
            headers=dict(self._headers),
            body=self._body,
            timeout=self._timeout,
        )

    # --- shortcut factories ---

    @classmethod
    def get(cls, url: str) -> "RequestBuilder":
        return cls().method("GET").url(url)

    @classmethod
    def post(cls, url: str) -> "RequestBuilder":
        return cls().method("POST").url(url)

    @classmethod
    def put(cls, url: str) -> "RequestBuilder":
        return cls().method("PUT").url(url)

    @classmethod
    def delete(cls, url: str) -> "RequestBuilder":
        return cls().method("DELETE").url(url)
