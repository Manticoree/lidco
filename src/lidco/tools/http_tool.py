"""
HTTP Request Tool — make arbitrary HTTP requests from the LIDCO CLI.

Supports GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS with headers, query params,
JSON body, form data, basic auth, bearer auth, and configurable timeout.

Uses only stdlib (urllib) — no requests/httpx dependency required.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HttpResponse:
    """Result of an HTTP request."""
    url: str
    method: str
    status: int
    reason: str
    headers: dict[str, str]
    body: str
    elapsed_ms: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        """Parse body as JSON. Raises ValueError on parse failure."""
        return json.loads(self.body)

    def format_summary(self) -> str:
        status_icon = "✓" if self.ok else "✗"
        lines = [
            f"{status_icon} {self.method} {self.url}",
            f"Status: {self.status} {self.reason}  ({self.elapsed_ms:.0f}ms)",
        ]
        ct = self.headers.get("content-type", "")
        if self.body:
            if "json" in ct:
                try:
                    pretty = json.dumps(self.json(), indent=2)
                    lines.append(f"Body:\n{pretty}")
                except ValueError:
                    lines.append(f"Body: {self.body[:500]}")
            else:
                lines.append(f"Body: {self.body[:500]}")
        if self.error:
            lines.append(f"Error: {self.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# HttpTool
# ---------------------------------------------------------------------------

class HttpTool:
    """
    Make HTTP requests using stdlib urllib.

    Parameters
    ----------
    default_timeout : float
        Default request timeout in seconds.
    default_headers : dict[str, str] | None
        Headers added to every request (can be overridden per-request).
    verify_ssl : bool
        If False, SSL certificate verification is disabled (use with care).
    """

    def __init__(
        self,
        default_timeout: float = 30.0,
        default_headers: dict[str, str] | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self._timeout = default_timeout
        self._default_headers: dict[str, str] = default_headers or {}
        self._verify_ssl = verify_ssl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        return self.request(
            "GET", url,
            params=params, headers=headers,
            timeout=timeout, auth=auth, bearer=bearer,
        )

    def post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        form_data: dict[str, str] | None = None,
        body: bytes | str | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        return self.request(
            "POST", url,
            params=params, headers=headers,
            json_data=json_data, form_data=form_data, body=body,
            timeout=timeout, auth=auth, bearer=bearer,
        )

    def put(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        form_data: dict[str, str] | None = None,
        body: bytes | str | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        return self.request(
            "PUT", url,
            params=params, headers=headers,
            json_data=json_data, form_data=form_data, body=body,
            timeout=timeout, auth=auth, bearer=bearer,
        )

    def delete(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        return self.request(
            "DELETE", url,
            params=params, headers=headers,
            timeout=timeout, auth=auth, bearer=bearer,
        )

    def patch(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        body: bytes | str | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        return self.request(
            "PATCH", url,
            params=params, headers=headers,
            json_data=json_data, body=body,
            timeout=timeout, auth=auth, bearer=bearer,
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        form_data: dict[str, str] | None = None,
        body: bytes | str | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
        bearer: str | None = None,
    ) -> HttpResponse:
        """
        Make an HTTP request.

        Parameters
        ----------
        method : str
            HTTP verb (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS).
        url : str
            Target URL (must start with http:// or https://).
        params : dict | None
            Query string parameters appended to url.
        headers : dict | None
            Per-request headers (merged with default_headers).
        json_data : Any
            JSON-serializable body. Sets Content-Type: application/json.
        form_data : dict | None
            URL-encoded form body. Sets Content-Type: application/x-www-form-urlencoded.
        body : bytes | str | None
            Raw request body (lower priority than json_data/form_data).
        timeout : float | None
            Override default_timeout for this request.
        auth : tuple[str, str] | None
            (username, password) for HTTP Basic authentication.
        bearer : str | None
            Bearer token for Authorization header.
        """
        method = method.upper()
        effective_timeout = timeout if timeout is not None else self._timeout

        # Build query string
        if params:
            qs = urllib.parse.urlencode(params)
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

        # Build headers
        merged_headers: dict[str, str] = {**self._default_headers}
        if headers:
            merged_headers.update(headers)

        # Auth
        if bearer:
            merged_headers["Authorization"] = f"Bearer {bearer}"
        elif auth:
            import base64
            token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            merged_headers["Authorization"] = f"Basic {token}"

        # Build body
        data: bytes | None = None
        if json_data is not None:
            data = json.dumps(json_data).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/json")
        elif form_data is not None:
            data = urllib.parse.urlencode(form_data).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif body is not None:
            data = body.encode("utf-8") if isinstance(body, str) else body

        req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)

        start = time.monotonic()
        try:
            ctx = None
            if not self._verify_ssl:
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=effective_timeout, context=ctx) as resp:
                elapsed = (time.monotonic() - start) * 1000
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                resp_body = resp.read().decode("utf-8", errors="replace")
                return HttpResponse(
                    url=url,
                    method=method,
                    status=resp.status,
                    reason=resp.reason,
                    headers=resp_headers,
                    body=resp_body,
                    elapsed_ms=elapsed,
                )
        except urllib.error.HTTPError as exc:
            elapsed = (time.monotonic() - start) * 1000
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            err_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            return HttpResponse(
                url=url,
                method=method,
                status=exc.code,
                reason=exc.reason or "",
                headers=err_headers,
                body=err_body,
                elapsed_ms=elapsed,
                error=str(exc),
            )
        except urllib.error.URLError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HttpResponse(
                url=url,
                method=method,
                status=0,
                reason="Connection error",
                headers={},
                body="",
                elapsed_ms=elapsed,
                error=str(exc.reason),
            )
        except TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return HttpResponse(
                url=url,
                method=method,
                status=0,
                reason="Timeout",
                headers={},
                body="",
                elapsed_ms=elapsed,
                error=f"Request timed out after {effective_timeout}s",
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.monotonic() - start) * 1000
            return HttpResponse(
                url=url,
                method=method,
                status=0,
                reason="Error",
                headers={},
                body="",
                elapsed_ms=elapsed,
                error=str(exc),
            )
