"""OAuth authorization code grant with PKCE (simulated, no actual HTTP)."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field


class OAuthError(Exception):
    """Raised on OAuth flow errors."""


@dataclass(frozen=True)
class OAuthConfig:
    """OAuth provider configuration."""

    client_id: str
    auth_url: str
    token_url: str
    redirect_uri: str = "http://localhost:8765/callback"
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PKCEChallenge:
    """PKCE code verifier / challenge pair."""

    verifier: str
    challenge: str
    method: str = "S256"


@dataclass(frozen=True)
class OAuthToken:
    """An OAuth access/refresh token."""

    access_token: str
    refresh_token: str = ""
    expires_at: float = 0.0
    token_type: str = "Bearer"
    scopes: tuple[str, ...] = ()


class OAuthFlow:
    """Simulated OAuth 2.0 authorization code flow with PKCE support."""

    def __init__(self, config: OAuthConfig) -> None:
        self._config = config

    # -- PKCE helpers --------------------------------------------------

    def generate_pkce(self) -> PKCEChallenge:
        """Generate a PKCE verifier/challenge pair."""
        verifier = secrets.token_urlsafe(32)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return PKCEChallenge(verifier=verifier, challenge=challenge, method="S256")

    # -- Authorization URL ---------------------------------------------

    def build_auth_url(
        self, state: str = "", pkce: PKCEChallenge | None = None
    ) -> str:
        """Build the authorization URL the user should visit."""
        params: dict[str, str] = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
        }
        if self._config.scopes:
            params["scope"] = " ".join(self._config.scopes)
        if state:
            params["state"] = state
        if pkce is not None:
            params["code_challenge"] = pkce.challenge
            params["code_challenge_method"] = pkce.method
        return f"{self._config.auth_url}?{urllib.parse.urlencode(params)}"

    # -- Token exchange (simulated) ------------------------------------

    def exchange_code(
        self, code: str, pkce: PKCEChallenge | None = None
    ) -> OAuthToken:
        """Simulate exchanging an authorization code for tokens."""
        if not code:
            raise OAuthError("Authorization code must not be empty")
        access = f"access_{code}_{secrets.token_hex(8)}"
        refresh = f"refresh_{code}_{secrets.token_hex(8)}"
        return OAuthToken(
            access_token=access,
            refresh_token=refresh,
            expires_at=time.time() + 3600,
            token_type="Bearer",
            scopes=self._config.scopes,
        )

    def refresh(self, token: OAuthToken) -> OAuthToken:
        """Simulate refreshing an expired token."""
        if not token.refresh_token:
            raise OAuthError("No refresh token available")
        new_access = f"access_refreshed_{secrets.token_hex(8)}"
        return OAuthToken(
            access_token=new_access,
            refresh_token=token.refresh_token,
            expires_at=time.time() + 3600,
            token_type=token.token_type,
            scopes=token.scopes,
        )

    # -- Helpers -------------------------------------------------------

    def is_expired(self, token: OAuthToken) -> bool:
        """Return True when the token's expiry time has passed."""
        if token.expires_at <= 0.0:
            return False
        return time.time() >= token.expires_at

    def revoke(self, token: OAuthToken) -> bool:
        """Simulate revoking a token. Always succeeds."""
        if not token.access_token:
            return False
        return True
