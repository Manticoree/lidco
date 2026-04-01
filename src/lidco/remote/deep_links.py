"""Deep link handler for URI-based actions — Q189, task 1060."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


_SCHEME = "lidco"
_VALID_ACTIONS = frozenset({
    "open",
    "session",
    "command",
    "file",
    "pair",
    "settings",
})


@dataclass(frozen=True)
class DeepLink:
    """Immutable parsed deep link."""

    scheme: str
    action: str
    params: dict[str, str]


class DeepLinkHandler:
    """Parse, generate, and validate ``lidco://`` deep links."""

    def parse(self, uri: str) -> DeepLink:
        """Parse a URI string into a DeepLink.

        Raises ValueError if the URI is invalid or uses an unsupported scheme.
        """
        parsed = urlparse(uri)
        scheme = parsed.scheme
        if not scheme:
            raise ValueError(f"Missing scheme in URI: {uri}")

        # Action is the host portion; path params are query-string style
        action = parsed.netloc or parsed.path.strip("/")
        if not action:
            raise ValueError(f"Missing action in URI: {uri}")

        # Flatten query params to single values
        raw_params = parse_qs(parsed.query, keep_blank_values=True)
        params = {k: v[0] if v else "" for k, v in raw_params.items()}

        return DeepLink(scheme=scheme, action=action, params=params)

    def generate(self, action: str, params: dict[str, str] | None = None) -> str:
        """Generate a ``lidco://`` deep link URI."""
        if not action:
            raise ValueError("Action must not be empty")
        qs = f"?{urlencode(params)}" if params else ""
        return f"{_SCHEME}://{action}{qs}"

    def validate(self, uri: str) -> bool:
        """Return True if *uri* is a well-formed lidco deep link."""
        try:
            link = self.parse(uri)
        except (ValueError, Exception):
            return False
        if link.scheme != _SCHEME:
            return False
        if link.action not in _VALID_ACTIONS:
            return False
        return True
