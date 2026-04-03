"""Session-level token authentication — Q259."""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass


@dataclass
class AuthToken:
    """A session authentication token."""

    token: str
    user: str
    role: str
    created_at: float
    expires_at: float
    refreshed_at: float | None = None


class SessionAuth:
    """Token-based session authentication with expiry and refresh."""

    def __init__(self, token_ttl: float = 3600.0) -> None:
        self._ttl = token_ttl
        self._tokens: dict[str, AuthToken] = {}

    def create_token(self, user: str, role: str = "viewer") -> AuthToken:
        """Create a new authentication token."""
        raw = f"{user}:{role}:{uuid.uuid4().hex}"
        token_str = hashlib.sha256(raw.encode()).hexdigest()[:48]
        now = time.time()
        token = AuthToken(
            token=token_str,
            user=user,
            role=role,
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._tokens[token_str] = token
        return token

    def validate(self, token: str) -> AuthToken | None:
        """Validate a token. Returns None if invalid or expired."""
        auth = self._tokens.get(token)
        if auth is None:
            return None
        if time.time() > auth.expires_at:
            del self._tokens[token]
            return None
        return auth

    def refresh(self, token: str) -> AuthToken | None:
        """Refresh a token, extending its expiry. Returns None if invalid."""
        auth = self.validate(token)
        if auth is None:
            return None
        now = time.time()
        auth.expires_at = now + self._ttl
        auth.refreshed_at = now
        return auth

    def revoke(self, token: str) -> bool:
        """Revoke a token."""
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False

    def active_sessions(self) -> list[AuthToken]:
        """Return all non-expired tokens."""
        now = time.time()
        active: list[AuthToken] = []
        expired_keys: list[str] = []
        for key, auth in self._tokens.items():
            if now > auth.expires_at:
                expired_keys.append(key)
            else:
                active.append(auth)
        for key in expired_keys:
            del self._tokens[key]
        return active

    def cleanup_expired(self) -> int:
        """Remove expired tokens. Returns count of removed."""
        now = time.time()
        expired = [k for k, v in self._tokens.items() if now > v.expires_at]
        for k in expired:
            del self._tokens[k]
        return len(expired)

    def summary(self) -> dict:
        """Return summary dict."""
        now = time.time()
        total = len(self._tokens)
        active = sum(1 for v in self._tokens.values() if now <= v.expires_at)
        return {
            "total_tokens": total,
            "active": active,
            "expired": total - active,
            "ttl": self._ttl,
        }
