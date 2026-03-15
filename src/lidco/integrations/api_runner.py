"""API test runner for making HTTP requests — Task 408."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class APIResponse:
    """Structured HTTP response."""

    status: int
    headers: dict[str, str]
    body: str
    elapsed_ms: float

    @property
    def is_json(self) -> bool:
        """True if the response body appears to be JSON."""
        ct = self.headers.get("content-type", "")
        return "application/json" in ct or _looks_like_json(self.body)

    def pretty_body(self) -> str:
        """Return pretty-printed body.  JSON is indented, others returned as-is."""
        if self.is_json:
            try:
                parsed = json.loads(self.body)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass
        return self.body

    def format(self) -> str:
        """Return a human-readable representation of the response."""
        lines: list[str] = [
            f"HTTP {self.status}  ({self.elapsed_ms:.0f} ms)",
            "",
        ]
        for name, value in self.headers.items():
            lines.append(f"{name}: {value}")
        lines.append("")
        body = self.pretty_body()
        if body:
            if self.is_json:
                lines.append("```json")
                lines.append(body)
                lines.append("```")
            else:
                lines.append(body)
        return "\n".join(lines)


class APIRunner:
    """Simple HTTP client with pretty-printing support.

    Args:
        base_url: Base URL prefix (e.g. ``https://api.example.com``).
        headers: Default headers sent with every request.
    """

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = dict(headers or {})

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_header(self, name: str, value: str) -> None:
        """Set or update a default header."""
        self._headers[name] = value

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> APIResponse:
        """Make an HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.).
            path: Request path or full URL.
            body: Request body.  Dicts are serialised as JSON automatically.
            params: Query string parameters.
            extra_headers: Per-request headers (override defaults).

        Returns:
            APIResponse with status, headers, body and elapsed_ms.

        Raises:
            RuntimeError: On network or URL errors.
        """
        url = self._build_url(path, params)

        all_headers = dict(self._headers)
        if extra_headers:
            all_headers.update(extra_headers)

        data: bytes | None = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                all_headers.setdefault("Content-Type", "application/json")
            elif isinstance(body, str):
                data = body.encode("utf-8")
                all_headers.setdefault("Content-Type", "text/plain")
            elif isinstance(body, bytes):
                data = body

        req = urllib.request.Request(
            url,
            data=data,
            headers=all_headers,
            method=method.upper(),
        )

        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed_ms = (time.monotonic() - start) * 1000
                resp_body = resp.read().decode("utf-8", errors="replace")
                resp_headers = {
                    k.lower(): v for k, v in resp.headers.items()
                }
                return APIResponse(
                    status=resp.status,
                    headers=resp_headers,
                    body=resp_body,
                    elapsed_ms=elapsed_ms,
                )
        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            headers_resp = {k.lower(): v for k, v in (exc.headers or {}).items()}
            return APIResponse(
                status=exc.code,
                headers=headers_resp,
                body=body_text,
                elapsed_ms=elapsed_ms,
            )
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Request failed: {exc.reason}") from exc

    # ------------------------------------------------------------------
    # Convenience shorthands
    # ------------------------------------------------------------------

    def get(self, path: str, params: dict | None = None, **kw: Any) -> APIResponse:
        return self.request("GET", path, params=params, **kw)

    def post(self, path: str, body: Any = None, **kw: Any) -> APIResponse:
        return self.request("POST", path, body=body, **kw)

    def put(self, path: str, body: Any = None, **kw: Any) -> APIResponse:
        return self.request("PUT", path, body=body, **kw)

    def patch(self, path: str, body: Any = None, **kw: Any) -> APIResponse:
        return self.request("PATCH", path, body=body, **kw)

    def delete(self, path: str, **kw: Any) -> APIResponse:
        return self.request("DELETE", path, **kw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self, path: str, params: dict[str, str] | None) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = self._base_url + "/" + path.lstrip("/")

        if params:
            query = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = url + sep + query

        return url


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _looks_like_json(text: str) -> bool:
    """Return True if text begins with a JSON object or array."""
    stripped = text.lstrip()
    return stripped.startswith(("{", "["))
