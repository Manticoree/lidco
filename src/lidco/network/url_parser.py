"""URL parsing and construction utilities — stdlib only."""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ParsedUrl:
    """Structured representation of a parsed URL."""

    scheme: str = ""
    host: str = ""
    port: Optional[int] = None
    path: str = ""
    query_params: dict[str, str] = field(default_factory=dict)
    fragment: str = ""


class UrlParser:
    """Parse, build, and manipulate URLs using urllib.parse."""

    def parse(self, url: str) -> ParsedUrl:
        """Parse a URL string into a ``ParsedUrl``."""
        p = urllib.parse.urlparse(url)
        host = p.hostname or ""
        port = p.port  # None when absent
        query_params: dict[str, str] = {}
        if p.query:
            for k, v_list in urllib.parse.parse_qs(p.query, keep_blank_values=True).items():
                query_params[k] = v_list[0] if v_list else ""
        return ParsedUrl(
            scheme=p.scheme,
            host=host,
            port=port,
            path=p.path,
            query_params=query_params,
            fragment=p.fragment,
        )

    def build(
        self,
        scheme: str,
        host: str,
        path: str = "/",
        *,
        port: Optional[int] = None,
        query_params: Optional[dict[str, str]] = None,
        fragment: str = "",
    ) -> str:
        """Construct a URL string from individual parts."""
        netloc = host
        if port is not None:
            netloc = f"{host}:{port}"
        query = urllib.parse.urlencode(query_params) if query_params else ""
        return urllib.parse.urlunparse((scheme, netloc, path, "", query, fragment))

    def add_query_params(self, url: str, params: dict[str, str]) -> str:
        """Append *params* to an existing URL's query string."""
        p = urllib.parse.urlparse(url)
        existing = urllib.parse.parse_qs(p.query, keep_blank_values=True)
        merged: dict[str, str] = {k: v[0] for k, v in existing.items() if v}
        merged.update(params)
        new_query = urllib.parse.urlencode(merged)
        return urllib.parse.urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))

    def is_valid(self, url: str) -> bool:
        """Return ``True`` if *url* has both a scheme and a host."""
        p = urllib.parse.urlparse(url)
        return bool(p.scheme) and bool(p.hostname)
