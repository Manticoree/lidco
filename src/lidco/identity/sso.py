"""SSOClient — SAML/OIDC client abstraction; token exchange; session binding."""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class SSOConfig:
    provider: str
    issuer_url: str
    client_id: str
    client_secret: str = ""
    protocol: str = "oidc"  # "oidc" or "saml"
    redirect_uri: str = ""


@dataclass(frozen=True)
class SSOSession:
    user_id: str
    provider: str
    token: str
    expires_at: float
    attributes: dict = field(default_factory=dict)


class SSOClient:
    """SAML/OIDC client abstraction with in-memory session store."""

    def __init__(self, config: SSOConfig) -> None:
        self._config = config
        self._sessions: dict[str, SSOSession] = {}

    def initiate_login(self) -> str:
        """Return an auth URL constructed from config."""
        base = self._config.issuer_url.rstrip("/")
        if self._config.protocol == "saml":
            return (
                f"{base}/saml/auth"
                f"?client_id={self._config.client_id}"
                f"&redirect_uri={self._config.redirect_uri}"
            )
        return (
            f"{base}/authorize"
            f"?client_id={self._config.client_id}"
            f"&redirect_uri={self._config.redirect_uri}"
            f"&response_type=code"
            f"&scope=openid+profile+email"
        )

    def exchange_token(self, code: str) -> SSOSession:
        """Simulate token exchange — return a new session."""
        raw = f"{self._config.client_id}:{code}:{time.time()}"
        token = hashlib.sha256(raw.encode()).hexdigest()
        user_id = str(uuid.uuid4())
        session = SSOSession(
            user_id=user_id,
            provider=self._config.provider,
            token=token,
            expires_at=time.time() + 3600.0,
            attributes={"code": code},
        )
        self._sessions[token] = session
        return session

    def validate_session(self, token: str) -> SSOSession | None:
        """Return session if valid and not expired, else None."""
        session = self._sessions.get(token)
        if session is None:
            return None
        if time.time() > session.expires_at:
            del self._sessions[token]
            return None
        return session

    def logout(self, token: str) -> bool:
        """Remove session. Return True if it existed."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def active_sessions(self) -> list[SSOSession]:
        """Return all non-expired sessions."""
        now = time.time()
        expired = [t for t, s in self._sessions.items() if now > s.expires_at]
        for t in expired:
            del self._sessions[t]
        return list(self._sessions.values())

    def refresh(self, token: str) -> SSOSession | None:
        """Refresh a session token, extending expiry."""
        old = self._sessions.pop(token, None)
        if old is None:
            return None
        if time.time() > old.expires_at:
            return None
        raw = f"{old.token}:{time.time()}"
        new_token = hashlib.sha256(raw.encode()).hexdigest()
        session = SSOSession(
            user_id=old.user_id,
            provider=old.provider,
            token=new_token,
            expires_at=time.time() + 3600.0,
            attributes=old.attributes,
        )
        self._sessions[new_token] = session
        return session

    def summary(self) -> dict:
        """Return summary info."""
        return {
            "provider": self._config.provider,
            "protocol": self._config.protocol,
            "issuer_url": self._config.issuer_url,
            "active_sessions": len(self.active_sessions()),
        }
