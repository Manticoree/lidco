"""Generate shareable session snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
import time


@dataclass(frozen=True)
class ShareLink:
    """Immutable representation of a shared session link."""

    id: str
    session_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 0
    anonymized: bool = False


_SENSITIVE_PATTERNS = (
    re.compile(r"(?:sk|pk|api)[_-][A-Za-z0-9\-]{16,}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?:token|secret|password|key)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
)


class ShareManager:
    """Create and manage shareable session links."""

    def __init__(self, default_expiry: float = 86400.0) -> None:
        self._default_expiry = default_expiry
        self._shares: dict[str, ShareLink] = {}
        self._contents: dict[str, str] = {}

    def create_share(
        self,
        session_id: str,
        content: str,
        anonymize: bool = False,
        expiry: float = 0.0,
    ) -> ShareLink:
        """Generate a share link, optionally anonymizing content."""
        effective_expiry = expiry if expiry > 0 else self._default_expiry
        share_id = hashlib.sha256(
            f"{session_id}-{time.time()}".encode()
        ).hexdigest()[:16]
        stored = self.anonymize(content) if anonymize else content
        link = ShareLink(
            id=share_id,
            session_id=session_id,
            expires_at=time.time() + effective_expiry,
            anonymized=anonymize,
        )
        self._shares[share_id] = link
        self._contents[share_id] = stored
        return link

    def anonymize(self, content: str) -> str:
        """Replace API keys, tokens, and emails with [REDACTED]."""
        result = content
        for pattern in _SENSITIVE_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result

    def is_expired(self, link: ShareLink) -> bool:
        """Return True if the link has expired."""
        if link.expires_at <= 0.0:
            return False
        return time.time() > link.expires_at

    def get_shares(self) -> list[ShareLink]:
        """Return all active (non-expired) share links."""
        return [s for s in self._shares.values() if not self.is_expired(s)]

    def revoke(self, share_id: str) -> bool:
        """Revoke a share by ID. Returns True if found and removed."""
        if share_id in self._shares:
            del self._shares[share_id]
            self._contents.pop(share_id, None)
            return True
        return False

    def summary(self) -> str:
        """Human-readable summary of shares."""
        active = self.get_shares()
        return f"Shares: {len(active)} active | default_expiry={self._default_expiry}s"
