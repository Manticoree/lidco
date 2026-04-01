"""Store and manage OAuth tokens per service."""

from __future__ import annotations

import time
from dataclasses import dataclass

from lidco.auth.oauth_flow import OAuthFlow, OAuthToken


@dataclass(frozen=True)
class StoredToken:
    """A token stored for a named service."""

    service: str
    token: OAuthToken
    created_at: float
    last_used: float


class TokenManager:
    """In-memory token store keyed by service name."""

    def __init__(self) -> None:
        self._tokens: dict[str, StoredToken] = {}

    def store(self, service: str, token: OAuthToken) -> None:
        """Store (or overwrite) a token for *service*."""
        now = time.time()
        self._tokens[service] = StoredToken(
            service=service,
            token=token,
            created_at=now,
            last_used=now,
        )

    def get(self, service: str) -> OAuthToken | None:
        """Return the token for *service*, or ``None``."""
        stored = self._tokens.get(service)
        if stored is None:
            return None
        # Update last_used (immutable dataclass → replace entry)
        self._tokens[service] = StoredToken(
            service=stored.service,
            token=stored.token,
            created_at=stored.created_at,
            last_used=time.time(),
        )
        return stored.token

    def remove(self, service: str) -> bool:
        """Remove the token for *service*. Return whether it existed."""
        return self._tokens.pop(service, None) is not None

    def list_services(self) -> list[str]:
        """Return all service names that have stored tokens."""
        return sorted(self._tokens)

    def is_expired(self, service: str) -> bool:
        """Return True if the token for *service* is expired (or missing)."""
        stored = self._tokens.get(service)
        if stored is None:
            return True
        tok = stored.token
        if tok.expires_at <= 0.0:
            return False
        return time.time() >= tok.expires_at

    def refresh_if_needed(self, service: str, flow: OAuthFlow) -> OAuthToken | None:
        """Refresh the token for *service* if expired. Return new token or None."""
        stored = self._tokens.get(service)
        if stored is None:
            return None
        if not self.is_expired(service):
            return stored.token
        new_token = flow.refresh(stored.token)
        self.store(service, new_token)
        return new_token

    def clear(self) -> int:
        """Remove all tokens. Return how many were removed."""
        count = len(self._tokens)
        self._tokens.clear()
        return count

    def token_count(self) -> int:
        """Return the number of stored tokens."""
        return len(self._tokens)
