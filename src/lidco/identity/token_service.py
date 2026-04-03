"""TokenService — JWT-like token creation/validation; refresh; revocation; claims."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    iss: str = "lidco"
    iat: float = 0.0
    exp: float = 0.0
    roles: list[str] = field(default_factory=list)
    custom: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Token:
    token: str
    claims: TokenClaims


class TokenService:
    """JWT-like token creation/validation with HMAC signing."""

    def __init__(self, secret: str = "lidco-secret", default_ttl: float = 3600.0) -> None:
        self._secret = secret
        self._default_ttl = default_ttl
        self._tokens: dict[str, Token] = {}  # token_str -> Token
        self._revoked: set[str] = set()

    def _sign(self, payload: dict) -> str:
        """Create HMAC-signed token string."""
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        encoded = base64.urlsafe_b64encode(raw.encode()).decode()
        sig = hmac.new(self._secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{sig}"

    def _verify(self, token_str: str) -> dict | None:
        """Verify signature and decode payload. None on failure."""
        parts = token_str.split(".")
        if len(parts) != 2:
            return None
        encoded, sig = parts
        expected = hmac.new(self._secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            raw = base64.urlsafe_b64decode(encoded.encode()).decode()
            return json.loads(raw)
        except Exception:
            return None

    def create(
        self,
        subject: str,
        roles: list[str] | None = None,
        ttl: float | None = None,
        custom: dict | None = None,
    ) -> Token:
        """Create a new token."""
        now = time.time()
        claims = TokenClaims(
            sub=subject,
            iss="lidco",
            iat=now,
            exp=now + (ttl if ttl is not None else self._default_ttl),
            roles=roles or [],
            custom=custom or {},
        )
        payload = asdict(claims)
        payload["jti"] = str(uuid.uuid4())
        token_str = self._sign(payload)
        tok = Token(token=token_str, claims=claims)
        self._tokens[token_str] = tok
        return tok

    def validate(self, token: str) -> TokenClaims | None:
        """Validate token. Return claims or None if invalid/expired/revoked."""
        if token in self._revoked:
            return None
        payload = self._verify(token)
        if payload is None:
            return None
        if time.time() > payload.get("exp", 0):
            self._tokens.pop(token, None)
            return None
        stored = self._tokens.get(token)
        if stored is not None:
            return stored.claims
        # Reconstruct claims from payload
        return TokenClaims(
            sub=payload["sub"],
            iss=payload.get("iss", "lidco"),
            iat=payload.get("iat", 0.0),
            exp=payload.get("exp", 0.0),
            roles=payload.get("roles", []),
            custom=payload.get("custom", {}),
        )

    def refresh(self, token: str) -> Token | None:
        """Refresh a token — revoke old, create new with same claims."""
        if token in self._revoked:
            return None
        old = self._tokens.get(token)
        if old is None:
            return None
        if time.time() > old.claims.exp:
            self._tokens.pop(token, None)
            return None
        self._revoked.add(token)
        self._tokens.pop(token, None)
        return self.create(
            subject=old.claims.sub,
            roles=list(old.claims.roles),
            custom=dict(old.claims.custom),
        )

    def revoke(self, token: str) -> bool:
        """Revoke a token. Return True if it was known."""
        if token in self._revoked:
            return False
        if token not in self._tokens:
            return False
        self._revoked.add(token)
        self._tokens.pop(token, None)
        return True

    def is_revoked(self, token: str) -> bool:
        return token in self._revoked

    def active_tokens(self) -> list[Token]:
        """Return non-expired, non-revoked tokens."""
        now = time.time()
        result = []
        expired = []
        for t, tok in self._tokens.items():
            if t in self._revoked:
                continue
            if now > tok.claims.exp:
                expired.append(t)
                continue
            result.append(tok)
        for t in expired:
            self._tokens.pop(t, None)
        return result

    def cleanup_expired(self) -> int:
        """Remove expired tokens. Return count removed."""
        now = time.time()
        expired = [t for t, tok in self._tokens.items() if now > tok.claims.exp]
        for t in expired:
            self._tokens.pop(t, None)
        return len(expired)

    def summary(self) -> dict:
        return {
            "total_tokens": len(self._tokens),
            "revoked": len(self._revoked),
            "active": len(self.active_tokens()),
        }
